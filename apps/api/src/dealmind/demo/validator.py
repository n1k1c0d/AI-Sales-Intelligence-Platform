"""Independent checks on business facts before opening a database connection."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from dealmind.models import Activity, Deal, DealStageHistory
from dealmind.models.enums import ActivityDirection, ActivityType, DealStatus, LossReason, UserRole

from .catalog import STAGES
from .dataset import Dataset, records, uid
from .scenarios import FIXTURES, status_of

MEANINGFUL = {ActivityType.CALL, ActivityType.MESSAGE, ActivityType.EMAIL, ActivityType.MEETING}


class InvalidDataset(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidDataset(message)


def check_examples(
    data: Dataset,
    deals: dict[UUID, Deal],
    events: dict[UUID, list[Activity]],
    histories: dict[UUID, list[DealStageHistory]],
) -> None:
    anchor = data.config.anchor_datetime
    require(
        set(data.references) == {f.key for f in FIXTURES}, "Missing mandatory scenario references"
    )
    stage_positions = {s.id: s.position // 10 - 1 for s in data.stages}
    for i, f in enumerate(FIXTURES):
        ref = data.references[f.key]
        require(ref == uid(f"deal:{i}") and ref in deals, f"{f.key}: wrong reference")
        d = deals[ref]
        chain = histories[ref]
        require(
            tuple(stage_positions[h.to_stage_id] for h in chain) == f.path,
            f"{f.key}: wrong stage path",
        )
        effective_end = d.closed_at or anchor
        expected_last = (
            None
            if f.contact_hours is None
            else min(effective_end, anchor - timedelta(hours=f.contact_hours))
        )
        require(d.last_activity_at == expected_last, f"{f.key}: unexpected customer contact age")
        expected_plan = (
            anchor + timedelta(seconds=f.follow_seconds)
            if f.follow_seconds is not None and d.status == DealStatus.OPEN
            else None
        )
        require(d.next_action_at == expected_plan, f"{f.key}: wrong follow-up")
        require(
            anchor - d.created_at == timedelta(days=f.age_days), f"{f.key}: incorrect opening time"
        )
        age = f.age_days if len(f.path) == 1 else f.stage_days
        require(
            anchor - chain[-1].changed_at == timedelta(days=age),
            f"{f.key}: incorrect time on stage",
        )
        if f.key in ("SYN-013", "SYN-R10"):
            require(
                any(
                    a.activity_type == ActivityType.NOTE
                    and d.last_activity_at is not None
                    and a.occurred_at > d.last_activity_at
                    for a in events[ref]
                ),
                f"{f.key}: missing subsequent note",
            )
        if f.late:
            require(
                any(a.created_at > a.occurred_at for a in events[ref]),
                f"{f.key}: missing late event",
            )
        if f.key == "SYN-003":
            require(
                any(a.activity_type == ActivityType.MEETING for a in events[ref]),
                "SYN-003: missing consultation",
            )
    for first, again in (("SYN-006", "SYN-009"), ("SYN-007", "SYN-008")):
        previous, current = deals[data.references[first]], deals[data.references[again]]
        require(
            previous.contact_id == current.contact_id
            and previous.closed_at is not None
            and previous.closed_at < current.created_at,
            f"{again}: invalid repeat opportunity",
        )


def validate(data: Dataset) -> None:
    c = data.config
    anchor = c.anchor_datetime
    expected_counts = {
        "organizations": 1,
        "users": c.managers_count + c.sales_leads_count,
        "contacts": c.contacts_count,
        "pipelines": 1,
        "pipeline_stages": len(STAGES),
        "deals": c.deals_count,
    }
    counts = data.counts()
    require(all(counts[k] == n for k, n in expected_counts.items()), "Entity count mismatch")
    org = data.organizations[0]
    pipe = data.pipelines[0]
    require(
        org.id == uid("organization")
        and org.name == c.organization_name
        and org.timezone == c.business_timezone
        and org.default_currency == c.currency
        and org.is_active,
        "Invalid demo organization",
    )
    require(pipe.id == uid("pipeline") and pipe.is_active, "Invalid demo pipeline")
    all_ids: set[object] = set()
    for model, rows in data.groups():
        seen_external: set[tuple[object, object]] = set()
        for row in records(model, rows):
            identifier = row["id"]
            require(
                isinstance(identifier, UUID)
                and identifier.version == 5
                and identifier not in all_ids,
                f"{model.__tablename__}: duplicate or invalid UUID",
            )
            all_ids.add(identifier)
            require(row.get("organization_id", org.id) == org.id, "Foreign organization")
            for name, val in row.items():
                if name.endswith("_at") and val is not None:
                    require(
                        isinstance(val, datetime) and val.utcoffset() is not None,
                        f"{name}: expected aware timestamp",
                    )
                    require(
                        isinstance(val, datetime) and (name == "next_action_at" or val <= anchor),
                        f"{name}: future event",
                    )
            start = row["created_at"]
            end = row.get("updated_at", start)
            require(
                isinstance(start, datetime) and isinstance(end, datetime) and start <= end,
                "Invalid record timestamps",
            )
            if "source_system" in row:
                pair = (row["source_system"], row.get("external_id", row.get("source_event_id")))
                require(
                    pair == (None, None)
                    or (
                        pair[0] == "demo_crm"
                        and isinstance(pair[1], str)
                        and bool(pair[1])
                        and pair not in seen_external
                    ),
                    "Invalid external identity",
                )
                seen_external.add(pair)
    require(
        Counter(u.role for u in data.users)
        == {UserRole.MANAGER: c.managers_count, UserRole.SALES_LEAD: c.sales_leads_count},
        "Sales team counts",
    )
    require(
        all(u.is_active and u.email and u.email.endswith("@example.invalid") for u in data.users),
        "Unsafe sales profile",
    )
    require(
        all(
            p.phone is None and p.email and p.email.endswith("@example.invalid")
            for p in data.contacts
        ),
        "Unsafe contact fields",
    )
    stages = {s.id: s for s in data.stages}
    require(
        sorted((s.code, s.position, s.stage_type, s.pipeline_id, s.is_active) for s in data.stages)
        == sorted(
            (code, (i + 1) * 10, status_of(i), pipe.id, True) for i, (code, _) in enumerate(STAGES)
        ),
        "Invalid pipeline stages",
    )
    deals = {d.id: d for d in data.deals}
    managers = {u.id for u in data.users if u.role == UserRole.MANAGER}
    users = {u.id for u in data.users}
    contacts = {p.id for p in data.contacts}
    require(Counter(d.status for d in data.deals) == c.quotas(), "Status quota mismatch")
    require(
        {d.loss_reason for d in data.deals if d.status == DealStatus.LOST} == set(LossReason),
        "Missing loss reasons",
    )
    events: dict[UUID, list[Activity]] = defaultdict(list)
    histories: dict[UUID, list[DealStageHistory]] = defaultdict(list)
    for a in data.activities:
        require(
            a.deal_id in deals and (a.actor_id is None or a.actor_id in users),
            "Unknown activity deal or actor",
        )
        d = deals[a.deal_id]
        require(
            a.activity_type in ActivityType
            and a.direction in ActivityDirection
            and ((a.activity_type in MEANINGFUL) == (a.direction != ActivityDirection.INTERNAL)),
            "Invalid activity kind/direction",
        )
        require(
            d.created_at <= a.occurred_at <= a.created_at <= (d.closed_at or anchor),
            "Invalid activity chronology",
        )
        require(isinstance(a.metadata_, dict), "Invalid activity metadata")
        events[d.id].append(a)
    for h in data.history:
        require(
            h.deal_id in deals
            and h.pipeline_id == pipe.id
            and h.to_stage_id in stages
            and (h.changed_by_id is None or h.changed_by_id in users),
            "Unknown history reference",
        )
        require(h.changed_at <= h.created_at <= anchor, "Invalid history timestamps")
        histories[h.deal_id].append(h)
    for d in data.deals:
        require(
            d.contact_id in contacts
            and d.owner_id in managers
            and d.pipeline_id == pipe.id
            and d.stage_id in stages,
            "Unknown deal reference",
        )
        require(d.status == stages[d.stage_id].stage_type, "Deal stage/status mismatch")
        require(
            isinstance(d.amount, Decimal)
            and d.amount.is_finite()
            and Decimal(0) <= d.amount <= Decimal("999999999999.99")
            and d.amount == d.amount.quantize(Decimal(".01")),
            "Invalid commercial amount",
        )
        require(
            d.currency in {c.currency, "RUB" if c.currency == "EUR" else "EUR"},
            "Invalid deal currency",
        )
        require(
            (d.status == DealStatus.OPEN) == (d.closed_at is None)
            and (d.status == DealStatus.LOST) == (d.loss_reason is not None)
            and (d.status != DealStatus.WON or d.amount > 0),
            "Invalid deal closure",
        )
        require(
            anchor - timedelta(days=c.history_days) <= d.created_at <= anchor
            and (d.closed_at is None or d.created_at <= d.closed_at <= d.updated_at),
            "Invalid deal chronology",
        )
        require(
            d.next_action_at is None
            or (d.status == DealStatus.OPEN and d.next_action_at >= d.created_at),
            "Invalid follow-up",
        )
        meaningful = [a.occurred_at for a in events[d.id] if a.activity_type in MEANINGFUL]
        require(
            d.last_activity_at == max(meaningful, default=None),
            "last_activity_at disagrees with customer contacts",
        )
        chain = histories[d.id]
        chain.sort(key=lambda h: h.sequence_no)
        require(
            bool(chain)
            and chain[0].changed_at == d.created_at
            and stages[chain[0].to_stage_id].code == "new_lead",
            "Missing initial history",
        )
        previous = None
        when = d.created_at
        for seq, h in enumerate(chain, 1):
            require(
                h.sequence_no == seq and h.from_stage_id == previous and h.to_stage_id != previous,
                "Invalid history chain",
            )
            require(
                when <= h.changed_at <= d.updated_at
                and (seq == len(chain) or stages[h.to_stage_id].stage_type == DealStatus.OPEN),
                "History chronology or premature terminal",
            )
            previous, when = h.to_stage_id, h.changed_at
        require(
            previous == d.stage_id and (d.closed_at is None or d.closed_at == when),
            "History final stage/time mismatch",
        )
    check_examples(data, deals, events, histories)
    require(data.digest() == data.fingerprint, "Dataset fingerprint mismatch")
