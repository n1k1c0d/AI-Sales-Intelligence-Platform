from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from dealmind.models.enums import DealStatus, LossReason

from .scenarios import FIXTURES

VERSION = "1.0.0"
type Ratio = Annotated[Decimal, Field(ge=0, le=1)]


def allocate(total: int, weights: list[Decimal]) -> list[int]:
    """Largest remainder; ties follow the declared category order."""
    weight_sum = sum(weights)
    exact = [total * w / weight_sum for w in weights]
    counts = [int(n) for n in exact]
    for i in sorted(range(len(counts)), key=lambda i: exact[i] - counts[i], reverse=True)[
        : total - sum(counts)
    ]:
        counts[i] += 1
    return counts


class Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dataset_name: Literal["dealmind-demo"] = "dealmind-demo"
    dataset_version: str = Field(default="1.0.0", min_length=1, max_length=32)
    organization_name: str = Field(default="DealMind Demo Academy", min_length=1, max_length=200)
    seed: int = Field(default=42, strict=True)
    anchor_datetime: AwareDatetime = datetime(2026, 11, 26, tzinfo=UTC)
    history_days: int = Field(default=180, ge=28, strict=True)
    managers_count: int = Field(default=8, gt=0, strict=True)
    sales_leads_count: int = Field(default=1, gt=0, strict=True)
    contacts_count: int = Field(default=600, ge=4, strict=True)
    deals_count: int = Field(default=800, gt=0, strict=True)
    open_ratio: Ratio = Decimal("0.45")
    won_ratio: Ratio = Decimal("0.30")
    lost_ratio: Ratio = Decimal("0.25")
    currency: str = Field(default="RUB", pattern=r"^[A-Z]{3}$")
    business_timezone: str = "Europe/Moscow"
    locale: Literal["ru_RU"] = "ru_RU"

    def quotas(self) -> dict[DealStatus, int]:
        return dict(
            zip(
                DealStatus,
                allocate(self.deals_count, [self.open_ratio, self.won_ratio, self.lost_ratio]),
                strict=True,
            )
        )

    @model_validator(mode="after")
    def check_scenarios(self) -> Self:
        if (
            not self.organization_name.strip()
            or self.organization_name != self.organization_name.strip()
        ):
            raise ValueError("Organization name must be nonblank and trimmed")
        try:
            ZoneInfo(self.business_timezone)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("Unknown IANA business timezone") from exc
        try:
            anchor = self.anchor_datetime.astimezone(UTC)
            _ = anchor - timedelta(days=self.history_days)
            _ = anchor + timedelta(days=5)
        except OverflowError as exc:
            raise ValueError(
                "Anchor, history window and follow-up must fit in datetime range"
            ) from exc
        if self.open_ratio + self.won_ratio + self.lost_ratio != 1:
            raise ValueError("Status ratios must sum to one")
        minimum = Counter(f.status for f in FIXTURES)
        minimum[DealStatus.LOST] = max(len(LossReason), self.managers_count)
        minimum[DealStatus.WON] = max(minimum[DealStatus.WON], self.managers_count)
        if any(self.quotas()[s] < n for s, n in minimum.items()):
            raise ValueError(
                f"Insufficient status quotas for mandatory scenarios and team: {dict(minimum)}"
            )
        return self
