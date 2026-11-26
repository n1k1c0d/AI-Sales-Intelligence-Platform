from collections import Counter, defaultdict
from decimal import Decimal
from uuid import UUID

from dealmind.models.enums import DealStatus

from .dataset import Dataset, configuration
from .validator import MEANINGFUL


def manifest(data: Dataset) -> dict[str, object]:
    stage = {s.id: s.code for s in data.stages}
    sums: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    follow: Counter[str] = Counter()
    for d in data.deals:
        sums[d.status][d.currency] += d.amount
        if d.status == DealStatus.OPEN:
            t = d.next_action_at
            category = (
                "missing"
                if t is None
                else "overdue"
                if t < data.config.anchor_datetime
                else "due_now"
                if t == data.config.anchor_datetime
                else "planned"
            )
            follow[category] += 1
    visits = Counter((h.deal_id, h.to_stage_id) for h in data.history)
    returns: set[UUID] = {deal for (deal, stage_id), n in visits.items() if n > 1}
    meaningful = sum(a.activity_type in MEANINGFUL for a in data.activities)
    return {
        **configuration(data.config),
        "organization_id": str(data.organizations[0].id),
        "pipeline_id": str(data.pipelines[0].id),
        "counts": data.counts(),
        "dataset_fingerprint": data.fingerprint,
        "deal_statuses": dict(Counter(d.status for d in data.deals)),
        "amounts_by_currency": {
            s: {c: format(n, ".2f") for c, n in currencies.items()}
            for s, currencies in sums.items()
        },
        "deals_by_manager": dict(Counter(str(d.owner_id) for d in data.deals)),
        "deals_by_stage": dict(Counter(stage[d.stage_id] for d in data.deals)),
        "loss_reasons": dict(
            Counter(d.loss_reason for d in data.deals if d.loss_reason is not None)
        ),
        "open_follow_up": dict(follow),
        "deals_with_stage_reentry": len(returns),
        "meaningful_activities": meaningful,
        "internal_activities": len(data.activities) - meaningful,
        "scenario_deals": {k: str(v) for k, v in data.references.items()},
    }
