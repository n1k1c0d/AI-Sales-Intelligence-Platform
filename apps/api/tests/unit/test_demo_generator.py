"""Generator contracts, scenario facts and failure modes without PostgreSQL."""

import json
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from dealmind.core.config import Settings
from dealmind.demo import cli, generator
from dealmind.demo.config import Config, allocate
from dealmind.demo.dataset import Dataset
from dealmind.demo.generator import generate
from dealmind.demo.manifest import manifest
from dealmind.demo.seeder import UnsafeTarget, check_target
from dealmind.demo.validator import InvalidDataset, validate
from dealmind.models.enums import ActivityType, DealStatus


@pytest.fixture
def small() -> Dataset:
    return generate(Config(deals_count=80, contacts_count=50, managers_count=3))


@pytest.mark.parametrize(
    "options",
    [
        {"managers_count": 0},
        {"contacts_count": 0},
        {"seed": 1.5},
        {"deals_count": 20},
        {"history_days": 20},
        {"open_ratio": "1.1"},
        {"won_ratio": "0.31"},
        {"anchor_datetime": "2026-11-26T00:00:00"},
        {"currency": "RUBB"},
        {"business_timezone": "Unknown/Nowhere"},
    ],
)
def test_invalid_config(options: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Config.model_validate(options)


def test_standard_manifest_matches_generated_dataset() -> None:
    data = generate(Config())
    validate(data)
    baseline = Path(__file__).resolve().parents[4] / "data/demo/dataset-manifest.json"
    assert manifest(data) == json.loads(baseline.read_text(encoding="utf-8"))
    assert data.config.anchor_datetime == datetime(2026, 11, 26, tzinfo=UTC)
    assert Counter(d.status for d in data.deals) == {"open": 360, "won": 240, "lost": 200}
    assert (
        len(data.contacts) == 600 and len(data.users) == 9 and 3000 <= len(data.activities) <= 5000
    )
    for owner in data.users[:8]:
        assert {d.status for d in data.deals if d.owner_id == owner.id} == set(DealStatus)
    assert any(n == 1 for n in Counter(d.contact_id for d in data.deals).values())
    assert {d.contact_id for d in data.deals} == {c.id for c in data.contacts}
    assert len(data.references) == 34


def test_reproducibility_and_clock(small: Dataset, monkeypatch: pytest.MonkeyPatch) -> None:
    class NoClock:
        @classmethod
        def now(cls, *args: object, **kwargs: object) -> datetime:
            raise AssertionError("Unexpected clock access")

    monkeypatch.setattr(generator, "datetime", NoClock)
    state = random.getstate()
    repeat = generate(small.config)
    assert random.getstate() == state
    assert small.digest() == repeat.digest() and small.references == repeat.references
    assert [d.id for d in small.deals] == [d.id for d in repeat.deals]
    repeat.activities.reverse()
    assert repeat.digest() == small.fingerprint
    different = generate(small.config.model_copy(update={"seed": 777}))
    assert different.fingerprint != small.fingerprint
    offset = Config.model_validate(
        {**small.config.model_dump(), "anchor_datetime": "2026-11-26T03:00:00+03:00"}
    )
    assert generate(offset).fingerprint == small.fingerprint
    assert allocate(7, [Decimal(1)] * 3) == [3, 2, 2]


def test_business_witnesses(small: Dataset) -> None:
    validate(small)
    by_id = {d.id: d for d in small.deals}
    refs = {k: by_id[v] for k, v in small.references.items()}
    anchor = small.config.anchor_datetime
    assert refs["SYN-007"].contact_id == refs["SYN-008"].contact_id
    first, repeat = refs["SYN-006"], refs["SYN-009"]
    assert first.status == repeat.status == DealStatus.WON and first.contact_id == repeat.contact_id
    assert first.closed_at and first.closed_at < repeat.created_at
    for n in (71, 72, 73):
        assert refs[f"B-H{n}"].last_activity_at == anchor - timedelta(hours=n)
    for days in (13, 14, 15):
        entries = [h for h in small.history if h.deal_id == refs[f"B-D{days}"].id]
        assert max(h.changed_at for h in entries) == anchor - timedelta(days=days)
    for label, offset in (("NOW", 0), ("BEFORE", -1), ("AFTER", 1)):
        assert refs[f"B-DUE-{label}"].next_action_at == anchor + timedelta(seconds=offset)
    stale = refs["SYN-R10"]
    assert stale.last_activity_at and stale.last_activity_at < anchor - timedelta(hours=72)
    assert any(
        a.activity_type == ActivityType.NOTE and a.occurred_at > stale.last_activity_at
        for a in small.activities
        if a.deal_id == stale.id
    )
    assert refs["SYN-R07"].next_action_at is None and refs["SYN-R07"].last_activity_at is None


@pytest.mark.parametrize(
    ("fault", "diagnostic"),
    [
        ("contact", "Unknown deal"),
        ("actor", "Unknown activity"),
        ("duplicate", "duplicate"),
        ("school", "Foreign organization"),
        ("pipeline", "pipeline stages"),
        ("stage", "stage/status"),
        ("amount", "commercial amount"),
        ("closed", "closure"),
        ("future", "future event"),
        ("sequence", "history chain"),
        ("from", "history chain"),
        ("changed", "chronology"),
        ("last", "last_activity_at"),
        ("scenario", "mandatory scenario"),
        ("fingerprint", "fingerprint"),
        ("note", "activity kind"),
        ("phone", "contact fields"),
    ],
)
def test_validator_rejects_corruption(small: Dataset, fault: str, diagnostic: str) -> None:
    d = small.deals[0]
    h = next(h for h in small.history if h.sequence_no == 2)
    match fault:
        case "contact":
            d.contact_id = uuid4()
        case "actor":
            small.activities[0].actor_id = uuid4()
        case "duplicate":
            small.contacts[0].id = small.users[0].id
        case "school":
            d.organization_id = uuid4()
        case "pipeline":
            small.stages[0].pipeline_id = uuid4()
        case "stage":
            d.stage_id = small.stages[-1].id
        case "amount":
            d.amount = Decimal("NaN")
        case "closed":
            d.closed_at = small.config.anchor_datetime
        case "future":
            small.activities[0].occurred_at = small.config.anchor_datetime + timedelta(days=1)
        case "sequence":
            h.sequence_no = 9
        case "from":
            h.from_stage_id = None
        case "changed":
            h.changed_at = small.deals[1].created_at - timedelta(days=1)
        case "last":
            d.last_activity_at = small.config.anchor_datetime
        case "scenario":
            small.references.pop("SYN-R01")
        case "fingerprint":
            small.fingerprint = "0" * 64
        case "note":
            small.activities[0].activity_type = ActivityType.NOTE
        case "phone":
            small.contacts[0].phone = "not-null"
    with pytest.raises(InvalidDataset, match=diagnostic):
        validate(small)


def test_dry_run_has_no_database_dependency(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("Dry run used database settings")

    monkeypatch.setattr(cli, "Settings", unexpected)
    path = tmp_path / "manifest.json"
    assert (
        cli.main(
            [
                "generate",
                "--deals",
                "80",
                "--contacts",
                "50",
                "--managers",
                "3",
                "--dry-run",
                "--manifest",
                str(path),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "DRY_RUN" and report["database_verification"] == "NOT_REQUESTED"
    assert (
        json.loads(path.read_text(encoding="utf-8"))["dataset_fingerprint"]
        == report["dataset_fingerprint"]
    )
    assert cli.main(["generate", "--managers", "-1"]) == 2


def test_seed_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        env="test",
        db_host="127.0.0.1",
        db_port=55433,
        db_name="dealmind_test",
        db_user="dealmind_test",
        db_password=SecretStr("synthetic"),
    )
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    assert cli.main(["seed"]) == 2
    for field, value in (("env", "production"), ("db_name", "dealmind"), ("db_host", "192.0.2.4")):
        with pytest.raises(UnsafeTarget):
            check_target(settings.model_copy(update={field: value}), True)
    monkeypatch.setattr(cli, "Settings", lambda: settings.model_copy(update={"env": "production"}))
    assert cli.main(["seed", "--apply"]) == 2
    with pytest.raises(UnsafeTarget):
        check_target(Settings(), True)
