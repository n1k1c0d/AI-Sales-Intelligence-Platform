import warnings

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapper, configure_mappers

from dealmind.db.base import Base
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
from dealmind.models.enums import (
    ActivityDirection,
    ActivityType,
    DealStatus,
    LossReason,
    StageType,
    UserRole,
)


def test_mappings_and_async_navigation() -> None:
    classes = (
        Organization,
        User,
        Contact,
        Pipeline,
        PipelineStage,
        Deal,
        Activity,
        DealStageHistory,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error", sa.exc.SAWarning)
        configure_mappers()
    assert set(Base.metadata.tables) == {model.__tablename__ for model in classes}
    assert len(Base.metadata.tables) == 8
    for model in classes:
        mapper = sa.inspect(model)
        assert isinstance(mapper, Mapper)
        table = Base.metadata.tables[model.__tablename__]
        assert list(table.primary_key.columns) == [table.c.id]
        assert isinstance(table.c.id.type, sa.Uuid) and table.c.id.default is not None
        assert all(c.name for c in table.constraints)
        for col in table.c:
            if col.name.endswith("_at"):
                assert isinstance(col.type, sa.DateTime) and col.type.timezone
        for rel in mapper.relationships:
            assert rel.lazy == "raise" and rel.viewonly
    assert Activity.metadata is Base.metadata
    assert Activity.metadata_.property.columns[0].name == "metadata"
    assert isinstance(Activity.metadata_.property.columns[0].type, JSONB)
    assert (Deal.amount.type.precision, Deal.amount.type.scale) == (14, 2)
    assert not Deal.owner_id.property.columns[0].nullable
    assert Activity.actor_id.property.columns[0].nullable
    assert DealStageHistory.from_stage_id.property.columns[0].nullable
    assert not DealStageHistory.to_stage_id.property.columns[0].nullable


def test_enum_storage_contract() -> None:
    for column, enum in [
        (User.role, UserRole),
        (PipelineStage.stage_type, StageType),
        (Deal.status, DealStatus),
        (Deal.loss_reason, LossReason),
        (Activity.activity_type, ActivityType),
        (Activity.direction, ActivityDirection),
    ]:
        assert isinstance(column.type, sa.Enum)
        assert column.type.enums == [item.value for item in enum]
        assert not column.type.native_enum and column.type.length == 32
