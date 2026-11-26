"""Generate, validate and optionally insert the reproducible DealMind demo dataset."""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from dealmind.core.config import Settings
from dealmind.db.engine import DatabaseUnavailable

from .config import Config
from .dataset import utc
from .generator import generate
from .manifest import manifest
from .seeder import Conflict, UnsafeTarget, VerificationError, check_target, seed
from .validator import InvalidDataset, validate


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    defaults = Config()
    for name, description in (
        ("generate", "Preview and validate locally"),
        ("seed", "Insert into a selected local demo/test database"),
    ):
        cmd = commands.add_parser(
            name,
            description=description,
            help=description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        for flag, field in (
            ("seed", "seed"),
            ("deals", "deals_count"),
            ("contacts", "contacts_count"),
            ("managers", "managers_count"),
            ("sales-leads", "sales_leads_count"),
            ("history-days", "history_days"),
        ):
            cmd.add_argument(
                "--" + flag,
                dest=field,
                type=int,
                default=getattr(defaults, field),
                help=field.replace("_", " "),
            )
        cmd.add_argument(
            "--anchor-date",
            dest="anchor_datetime",
            default=utc(defaults.anchor_datetime),
            help="ISO 8601 observation time with offset",
        )
        for field in (
            "dataset_version",
            "organization_name",
            "business_timezone",
            "currency",
            "open_ratio",
            "won_ratio",
            "lost_ratio",
        ):
            cmd.add_argument(
                "--" + field.replace("_", "-"),
                dest=field,
                default=str(getattr(defaults, field)),
                help=field.replace("_", " "),
            )
        if name == "generate":
            cmd.add_argument(
                "--dry-run", action="store_true", help="Preview only (already the default)"
            )
            cmd.add_argument(
                "--manifest", type=Path, help="Write the validated manifest as UTF-8 JSON"
            )
        else:
            cmd.add_argument(
                "--apply", action="store_true", help="Authorize the insert transaction"
            )
    return root


def main(argv: list[str] | None = None) -> int:
    options = vars(parser().parse_args(argv))
    operation = options.pop("command")
    apply = options.pop("apply", False)
    destination = options.pop("manifest", None)
    options.pop("dry_run", None)
    try:
        config = Config.model_validate(options)
        settings = None
        if operation == "seed":
            settings = Settings()
            check_target(settings, apply)
            print(
                f"Target: {settings.env} {settings.db_host}:{settings.db_port}/{settings.db_name}",
                file=sys.stderr,
                flush=True,
            )
        data = generate(config)
        validate(data)
        summary = manifest(data)
        if settings is None:
            if destination is not None:
                destination.write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            result = {"status": "DRY_RUN", "database_verification": "NOT_REQUESTED"}
        else:
            outcome = asyncio.run(
                seed(data, settings, apply=apply),
                loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None,
            )
            result = {**asdict(outcome), "database_verification": "VERIFIED"}
        print(json.dumps({**summary, **result, "validation": "PASS"}, indent=2, sort_keys=True))
        return 0
    except ValidationError as exc:
        for error in exc.errors(include_input=False, include_url=False):
            print(f"{'.'.join(map(str, error['loc']))}: {error['msg']}", file=sys.stderr)
        return 2
    except (UnsafeTarget, InvalidDataset) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Conflict as exc:
        print(f"CONFLICT: {exc}", file=sys.stderr)
        return 3
    except VerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, SQLAlchemyError, DatabaseUnavailable) as exc:
        print(
            f"Execution failed ({type(exc).__name__}); check target and configuration.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
