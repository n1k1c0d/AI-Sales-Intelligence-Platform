"""Round-trip all eight mappings through the same async session factory as the API."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import selectinload

from dealmind.core.config import Settings
from dealmind.db.engine import create_database_engine
from dealmind.db.session import create_session_factory
from dealmind.models import (
    Activity,
    Contact,
    Deal,
    DealStageHistory,
    Organization,
    Pipeline,
    PipelineStage,
    User,
)
from dealmind.models.enums import ActivityDirection, ActivityType, DealStatus, StageType, UserRole

pytestmark = pytest.mark.database


@pytest.mark.asyncio
async def test_crm_round_trip(crm_settings: Settings) -> None:
    engine = create_database_engine(crm_settings)
    sessions = create_session_factory(engine)
    moment = datetime(2026, 1, 10, 12, tzinfo=timezone(timedelta(hours=3)))
    closed = moment + timedelta(hours=2)
    amount = Decimal("999999999999.99")
    try:
        async with sessions.begin() as session:
            school = Organization(name="Fixture school", timezone="UTC", default_currency="RUB")
            session.add(school)
            await session.flush()
            assert isinstance(school.id, UUID) and school.id.version == 4 and school.is_active
            contact = Contact(organization_id=school.id, full_name="Fixture contact")
            manager = User(
                organization_id=school.id, full_name="Fixture manager", role=UserRole.MANAGER
            )
            pipeline = Pipeline(organization_id=school.id, name="Fixture pipeline", code="main")
            session.add_all([contact, manager, pipeline])
            await session.flush()
            assert not pipeline.is_active
            stages = [
                PipelineStage(
                    organization_id=school.id,
                    pipeline_id=pipeline.id,
                    name=kind.value,
                    code=kind.value,
                    position=index,
                    stage_type=kind,
                )
                for index, kind in enumerate(StageType)
            ]
            session.add_all(stages)
            await session.flush()
            first, won, _lost = stages
            pipeline.is_active = True
            purchases = [
                Deal(
                    organization_id=school.id,
                    pipeline_id=pipeline.id,
                    owner_id=manager.id,
                    contact_id=contact.id,
                    stage_id=first.id,
                    title=title,
                    amount=amount,
                    currency="RUB",
                    status=DealStatus.OPEN,
                    created_at=moment,
                )
                for title in ("First purchase", "Repeat purchase")
            ]
            session.add_all(purchases)
            await session.flush()
            deal, repeat = purchases
            for purchase in purchases:
                session.add(
                    DealStageHistory(
                        organization_id=school.id,
                        pipeline_id=pipeline.id,
                        deal_id=purchase.id,
                        to_stage_id=first.id,
                        sequence_no=1,
                        changed_at=moment,
                    )
                )
            call = Activity(
                organization_id=school.id,
                deal_id=deal.id,
                actor_id=manager.id,
                activity_type=ActivityType.CALL,
                direction=ActivityDirection.INBOUND,
                occurred_at=moment,
                metadata_={"channel": "test", "tags": ["a"]},
            )
            note = Activity(
                organization_id=school.id,
                deal_id=deal.id,
                actor_id=None,
                activity_type=ActivityType.NOTE,
                direction=ActivityDirection.INTERNAL,
                occurred_at=moment,
            )
            deal.last_activity_at = moment
            session.add_all([call, note])
            deal.status, deal.stage_id, deal.closed_at = DealStatus.WON, won.id, closed
            session.add(
                DealStageHistory(
                    organization_id=school.id,
                    pipeline_id=pipeline.id,
                    deal_id=deal.id,
                    from_stage_id=first.id,
                    to_stage_id=won.id,
                    changed_by_id=manager.id,
                    sequence_no=2,
                    changed_at=closed,
                )
            )

        async with sessions.begin() as session:
            loaded = (
                await session.scalars(
                    sa.select(Deal)
                    .where(Deal.id == deal.id)
                    .options(
                        selectinload(Deal.contact).selectinload(Contact.deals),
                        selectinload(Deal.owner),
                        selectinload(Deal.stage),
                        selectinload(Deal.pipeline).selectinload(Pipeline.stages),
                        selectinload(Deal.activities).selectinload(Activity.actor),
                        selectinload(Deal.stage_history).selectinload(DealStageHistory.from_stage),
                        selectinload(Deal.stage_history).selectinload(DealStageHistory.to_stage),
                        selectinload(Deal.stage_history).selectinload(DealStageHistory.changed_by),
                    )
                )
            ).one()
            assert loaded.amount == amount and isinstance(loaded.amount, Decimal)
            assert loaded.created_at == moment.astimezone(UTC) and loaded.closed_at == closed
            assert loaded.created_at.utcoffset() is not None
            assert loaded.status is DealStatus.WON and loaded.stage.stage_type is StageType.WON
            assert [s.id for s in loaded.pipeline.stages] == [s.id for s in stages]
            assert {d.id for d in loaded.contact.deals} == {deal.id, repeat.id}
            assert loaded.owner.role is UserRole.MANAGER
            initial, final = loaded.stage_history
            assert initial.from_stage is None and initial.changed_by is None
            assert initial.to_stage.id == first.id and initial.sequence_no == 1
            assert (
                final.from_stage and final.from_stage.id == first.id and final.to_stage.id == won.id
            )
            assert final.sequence_no == 2 and final.changed_by is loaded.owner
            events = {a.id: a for a in loaded.activities}
            assert events[call.id].actor is loaded.owner
            assert events[call.id].metadata_ == {"channel": "test", "tags": ["a"]}
            assert events[note.id].metadata_ == {} and events[note.id].actor is None
            with pytest.raises(sa.exc.InvalidRequestError, match="lazy='raise'"):
                _ = events[note.id].deal
            before = loaded.owner.updated_at
            loaded.owner.is_active = False

        # DB-051..054: ORM deletion, including a parent with an eagerly loaded collection.
        async with sessions() as session:
            for parent in (contact, manager, won):
                with pytest.raises(sa.exc.IntegrityError) as error:
                    async with session.begin():
                        if isinstance(parent, Contact):
                            target = await session.get(
                                Contact, parent.id, options=[selectinload(Contact.deals)]
                            )
                            assert target and len(target.deals) == 2
                            await session.delete(target)
                        else:
                            persistent = await session.get(type(parent), parent.id)
                            assert persistent is not None
                            await session.delete(persistent)
                assert getattr(error.value.orig, "sqlstate", None) == "23503"

            persisted = await session.get(User, manager.id)
            assert persisted and not persisted.is_active and persisted.updated_at >= before
            transition = await session.get(DealStageHistory, final.id)
            assert transition and transition.changed_by_id == manager.id
            assert (
                await session.scalars(sa.select(Deal.owner_id).where(Deal.id == deal.id))
            ).one() == manager.id
            assert (
                await session.scalars(sa.select(Activity.actor_id).where(Activity.id == call.id))
            ).one() == manager.id
            draft = Organization(name="Rollback fixture", timezone="UTC", default_currency="RUB")
            session.add(draft)
            await session.flush()
            rolled_back = draft.id
            await session.rollback()
        async with sessions() as session:
            assert await session.get(Organization, rolled_back) is None
    finally:
        await engine.dispose()
