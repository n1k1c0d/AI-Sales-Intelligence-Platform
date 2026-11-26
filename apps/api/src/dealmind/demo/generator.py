import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from random import Random
from zoneinfo import ZoneInfo

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
from dealmind.models.enums import ActivityDirection, ActivityType, DealStatus, LossReason, UserRole

from .catalog import LOSS_NOTES, LOSS_WEIGHTS, MESSAGES, PROFILES, PROGRAMS, STAGES
from .config import Config, allocate
from .dataset import Dataset, canonical, configuration, uid
from .scenarios import FIXTURES, Fixture, status_of


@dataclass(frozen=True)
class Journey:
    path: tuple[int, ...]
    opened: datetime
    entered: datetime
    last_contact: datetime | None
    plan: datetime | None
    note: datetime | None
    late: bool = False


def controlled(f: Fixture, anchor: datetime) -> Journey:
    opened = anchor - timedelta(days=f.age_days)
    entered = opened if len(f.path) == 1 else anchor - timedelta(days=f.stage_days)
    end = anchor if f.status == DealStatus.OPEN else entered
    contact = (
        min(end, anchor - timedelta(hours=f.contact_hours)) if f.contact_hours is not None else None
    )
    follow = (
        anchor + timedelta(seconds=f.follow_seconds)
        if f.status == DealStatus.OPEN and f.follow_seconds is not None
        else None
    )
    note = anchor - timedelta(hours=1) if f.key in ("SYN-013", "SYN-R10") else None
    return Journey(f.path, opened, entered, contact, follow, note, f.late)


def regular(rng: Random, config: Config, status: DealStatus, owner: int) -> Journey:
    anchor = config.anchor_datetime.astimezone(UTC)
    profile = PROFILES[owner % len(PROFILES)]
    age = rng.randint(1, config.history_days * 86400)
    opened = anchor - timedelta(seconds=age)
    if (
        opened.astimezone(ZoneInfo(config.business_timezone)).weekday() >= 5
        and age > 86400
        and rng.randrange(4)
    ):
        opened += timedelta(days=1)
    available = int((anchor - opened).total_seconds())
    path = (0, *sorted(rng.sample(range(1, 6), rng.randint(0, 5))))
    if status != DealStatus.OPEN:
        path += (6 if status == DealStatus.WON else 7,)
    span = min(available, 86400 * rng.randint(1, profile.cycle_days * 2))
    entered = opened + timedelta(seconds=rng.randint(0, span)) if len(path) > 1 else opened
    end = anchor if status == DealStatus.OPEN else entered
    last = end - timedelta(seconds=rng.randint(0, int((end - opened).total_seconds())))
    planned = None
    if status == DealStatus.OPEN:
        roll = rng.randrange(100)
        if roll < profile.overdue_percent:
            planned = max(opened, anchor - timedelta(hours=rng.randint(1, 120)))
        elif roll >= profile.overdue_percent + 18:
            planned = anchor + timedelta(hours=rng.randint(1, 120))
    note = end if rng.randrange(3) == 0 or status == DealStatus.LOST else None
    return Journey(path, opened, entered, last, planned, note, rng.randrange(8) == 0)


def foundation(data: Dataset) -> None:
    c = data.config
    start = c.anchor_datetime.astimezone(UTC) - timedelta(days=c.history_days)
    org, pipe = uid("organization"), uid("pipeline")
    stamps = dict(created_at=start, updated_at=start)
    data.organizations.append(
        Organization(
            id=org,
            name=c.organization_name,
            timezone=c.business_timezone,
            default_currency=c.currency,
            is_active=True,
            **stamps,
        )
    )
    # Persists configuration identity even if a parameter change happens to yield identical records.
    signature = hashlib.sha256(canonical(configuration(c))).hexdigest()
    data.pipelines.append(
        Pipeline(
            id=pipe,
            organization_id=org,
            name="Демонстрационные продажи",
            code="demo_sales",
            description=f"DealMind synthetic dataset {signature}",
            is_active=True,
            **stamps,
        )
    )
    for i, (code, name) in enumerate(STAGES):
        data.stages.append(
            PipelineStage(
                id=uid(f"stage:{code}"),
                organization_id=org,
                pipeline_id=pipe,
                name=name,
                code=code,
                position=(i + 1) * 10,
                stage_type=status_of(i),
                is_active=True,
                **stamps,
            )
        )
    for role, count in (
        (UserRole.MANAGER, c.managers_count),
        (UserRole.SALES_LEAD, c.sales_leads_count),
    ):
        for i in range(count):
            data.users.append(
                User(
                    id=uid(f"{role}:{i}"),
                    organization_id=org,
                    role=role,
                    full_name=f"{'Менеджер' if role == UserRole.MANAGER else 'Руководитель'} Академии {i + 1:02}",
                    email=f"{role}{i + 1:02}@example.invalid",
                    is_active=True,
                    **stamps,
                )
            )
    for i in range(c.contacts_count):
        data.contacts.append(
            Contact(
                id=uid(f"contact:{i}"),
                organization_id=org,
                full_name=f"Учащийся Академии {i + 1:04}",
                email=f"contact{i + 1:04}@example.invalid",
                phone=None,
                source_system="demo_crm" if i % 3 else None,
                external_id=f"C-{i + 1:06}" if i % 3 else None,
                **stamps,
            )
        )


def history(data: Dataset, deal: Deal, j: Journey) -> None:
    for i, index in enumerate(j.path):
        changed = j.opened + (j.entered - j.opened) * i / max(1, len(j.path) - 1)
        data.history.append(
            DealStageHistory(
                id=uid(f"{deal.id}:transition:{i}"),
                organization_id=deal.organization_id,
                deal_id=deal.id,
                pipeline_id=deal.pipeline_id,
                from_stage_id=data.stages[j.path[i - 1]].id if i else None,
                to_stage_id=data.stages[index].id,
                changed_by_id=deal.owner_id,
                sequence_no=i + 1,
                changed_at=changed,
                created_at=changed,
                source_system=None,
                source_event_id=None,
            )
        )


def activities(
    data: Dataset, deal: Deal, j: Journey, owner: int, rng: Random, scenario: str | None
) -> None:
    end = deal.closed_at or data.config.anchor_datetime.astimezone(UTC)
    events: list[Activity] = []

    def event(
        kind: ActivityType, when: datetime, summary: str, direction: ActivityDirection
    ) -> None:
        recorded = min(end, when + timedelta(hours=3)) if j.late else when
        events.append(
            Activity(
                id=uid(f"{deal.id}:activity:{len(events)}"),
                organization_id=deal.organization_id,
                deal_id=deal.id,
                actor_id=deal.owner_id,
                activity_type=kind,
                direction=direction,
                occurred_at=when,
                summary=summary,
                metadata_={},
                created_at=recorded,
            )
        )

    if j.last_contact is not None:
        typical = PROFILES[owner % len(PROFILES)].communications
        count = max(1, typical + rng.randint(-2, 2) - int(end - j.opened < timedelta(days=3)))
        for i in range(1, count + 1):
            when = j.opened + (j.last_contact - j.opened) * i / count
            kind = rng.choice(tuple(MESSAGES))
            summary = rng.choice(MESSAGES[kind])
            if i == count and scenario in ("SYN-002", "SYN-003", "SYN-004", "SYN-005"):
                kind, summary = {
                    "SYN-002": (ActivityType.CALL, "Провели квалификацию клиента."),
                    "SYN-003": (ActivityType.MEETING, "Провели консультацию по учебной программе."),
                    "SYN-004": (
                        ActivityType.EMAIL,
                        "Обсудили отправленное коммерческое предложение.",
                    ),
                    "SYN-005": (
                        ActivityType.MESSAGE,
                        "Клиент сравнивает программы и примет решение позже.",
                    ),
                }[scenario]
            event(
                kind,
                when,
                summary,
                rng.choice((ActivityDirection.INBOUND, ActivityDirection.OUTBOUND)),
            )
    if j.note is not None:
        kind = (
            ActivityType.NOTE
            if deal.loss_reason or j.note < end
            else rng.choice((ActivityType.NOTE, ActivityType.TASK))
        )
        text = (
            LOSS_NOTES[deal.loss_reason]
            if deal.loss_reason
            else "Зафиксировали вопросы для следующей консультации."
        )
        event(kind, j.note, text, ActivityDirection.INTERNAL)
    data.activities.extend(events)
    deal.last_activity_at = max(
        (a.occurred_at for a in events if a.activity_type in MESSAGES), default=None
    )
    deal.updated_at = max([j.entered, *(a.created_at for a in events)])


def generate(config: Config) -> Dataset:
    rng = Random(config.seed)
    data = Dataset(config)
    foundation(data)
    anchor = config.anchor_datetime.astimezone(UTC)
    quotas = config.quotas()
    reserved = Counter(f.status for f in FIXTURES)
    statuses = [s for s in DealStatus for _ in range(quotas[s] - reserved[s])]
    rng.shuffle(statuses)
    statuses = [f.status for f in FIXTURES] + statuses
    owners = {}
    for k, s in enumerate(DealStatus):
        # Every manager has a win and a loss. Profiles allocate the remaining quota.
        initial = list(range(min(config.managers_count, quotas[s])))
        pool = initial + rng.choices(
            range(config.managers_count),
            weights=[
                PROFILES[i % len(PROFILES)].status_weights[k] for i in range(config.managers_count)
            ],
            k=quotas[s] - len(initial),
        )
        rng.shuffle(pool)
        owners[s] = pool
    # One slot per reason first; standard quotas follow the requested weighted proportions.
    loss_counts = allocate(quotas[DealStatus.LOST], [Decimal(w) for w in LOSS_WEIGHTS])
    for i, count in enumerate(loss_counts):
        if count == 0:
            donor = max(range(len(loss_counts)), key=loss_counts.__getitem__)
            loss_counts[donor] -= 1
            loss_counts[i] += 1
    reasons = [r for r, n in zip(LossReason, loss_counts, strict=True) for _ in range(n)]
    rng.shuffle(reasons)
    contact_order = list(range(3, config.contacts_count))
    rng.shuffle(contact_order)
    next_contact = 0
    for i, status in enumerate(statuses):
        fixture = FIXTURES[i] if i < len(FIXTURES) else None
        owner = owners[status].pop()
        j = controlled(fixture, anchor) if fixture else regular(rng, config, status, owner)
        if fixture and fixture.contact_slot is not None:
            contact = fixture.contact_slot
        elif i == 0:
            contact = 2
        else:
            contact = contact_order[next_contact % len(contact_order)]
            next_contact += 1
        program, base, eur = rng.choice(PROGRAMS)
        currency = (
            ("EUR" if config.currency != "EUR" else "RUB") if i % 53 == 0 else config.currency
        )
        amount = ((eur if currency == "EUR" else base) * (100 - rng.randint(0, 25)) / 100).quantize(
            Decimal("0.01")
        )
        deal = Deal(
            id=uid(f"deal:{i}"),
            organization_id=data.organizations[0].id,
            contact_id=data.contacts[contact].id,
            owner_id=data.users[owner].id,
            pipeline_id=data.pipelines[0].id,
            stage_id=data.stages[j.path[-1]].id,
            title=f"{program} · набор {i + 1:04}",
            amount=amount,
            currency=currency,
            status=status,
            loss_reason=reasons.pop() if status == DealStatus.LOST else None,
            created_at=j.opened,
            closed_at=j.entered if status != DealStatus.OPEN else None,
            next_action_at=j.plan,
            source_system="demo_crm" if i % 3 else None,
            external_id=f"D-{i + 1:06}" if i % 3 else None,
        )
        data.deals.append(deal)
        if fixture:
            data.references[fixture.key] = deal.id
        history(data, deal, j)
        activities(data, deal, j, owner, rng, fixture.key if fixture else None)
    data.fingerprint = data.digest()
    return data
