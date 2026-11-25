"""Reject empty, skipped or unsuccessful suites and incomplete DB integration runs."""
import argparse
from xml.etree import ElementTree

DATABASE_CASES = {
    "test_transaction_visibility_and_cleanup", "test_baseline_round_trip_on_fresh_database",
    "test_recovery_without_app_restart", "test_probe_timeout_while_pool_is_exhausted",
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--database", action="store_true")
    args = parser.parse_args()
    cases = ElementTree.parse(args.report).findall(".//testcase")
    names = {case.get("name", "").partition("[")[0] for case in cases}
    failed = sum(case.find("failure") is not None or case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    print(f"{len(cases)} tests, {failed} failed, {skipped} skipped")
    if not cases or skipped or failed:
        raise SystemExit("Expected a nonempty fully passing suite")
    if args.database and DATABASE_CASES - names:
        raise SystemExit("Missing database tests: " + ", ".join(sorted(DATABASE_CASES - names)))
