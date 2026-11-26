"""Named reference deals. Offsets are relative to the configured observation time."""

from dataclasses import dataclass

from dealmind.models.enums import DealStatus


@dataclass(frozen=True)
class Fixture:
    key: str
    path: tuple[int, ...]
    age_days: int = 26
    stage_days: int = 2
    contact_hours: int | None = 12
    follow_seconds: int | None = 86400
    contact_slot: int | None = None
    late: bool = False

    @property
    def status(self) -> DealStatus:
        return status_of(self.path[-1])


def status_of(stage: int) -> DealStatus:
    return {6: DealStatus.WON, 7: DealStatus.LOST}.get(stage, DealStatus.OPEN)


FIXTURES = (
    Fixture("SYN-001", (0,), 1, contact_hours=None),
    Fixture("SYN-002", (0, 1, 2)),
    Fixture("SYN-003", (0, 1, 2, 3)),
    Fixture("SYN-004", (0, 2, 4)),
    Fixture("SYN-005", (0, 2, 4, 5)),
    Fixture("SYN-006", (0, 2, 4, 6), 28, 18, contact_slot=0),
    Fixture("SYN-007", (0, 1, 7), 28, 20, contact_slot=1),
    Fixture("SYN-008", (0, 1), 8, contact_slot=1),
    Fixture("SYN-009", (0, 3, 6), 10, 2, contact_slot=0),
    Fixture("SYN-010", (0, 1, 3, 2)),
    Fixture("SYN-011", (0, 3)),
    Fixture("SYN-012", (0, 1, 3, 1, 3)),
    Fixture("SYN-013", (0, 1), contact_hours=48),
    Fixture("SYN-014", (0, 1), late=True),
    Fixture("SYN-R01", (0, 1)),
    Fixture("SYN-R02", (0, 1), contact_hours=96),
    Fixture("SYN-R03", (0, 1), follow_seconds=None),
    Fixture("SYN-R04", (0, 1), follow_seconds=-3600),
    Fixture("SYN-R05", (0, 2), stage_days=18),
    Fixture("SYN-R06", (0,), contact_hours=None, follow_seconds=-3600),
    Fixture("SYN-R07", (0, 1), stage_days=20, contact_hours=None, follow_seconds=None),
    Fixture("SYN-R08", (0,), 1, contact_hours=None),
    Fixture("SYN-R09", (0,), 25, contact_hours=None),
    Fixture("SYN-R10", (0, 1), contact_hours=120),
    Fixture("SYN-R11", (0, 2, 6)),
    *(Fixture(f"B-H{h}", (0, 1), contact_hours=h) for h in (71, 72, 73)),
    *(Fixture(f"B-D{d}", (0, 1), stage_days=d) for d in (13, 14, 15)),
    Fixture("B-DUE-NOW", (0, 1), follow_seconds=0),
    Fixture("B-DUE-BEFORE", (0, 1), follow_seconds=-1),
    Fixture("B-DUE-AFTER", (0, 1), follow_seconds=1),
)
