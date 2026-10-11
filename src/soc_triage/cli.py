"""Offline SOC case ingestion and audited workflow commands."""

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from soc_triage.inventory import load_inventory, lookup_asset
from soc_triage.parsing import parse_alert
from soc_triage.storage import CaseStore
from soc_triage.workflow import transition_case


def audit_time(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Use an ISO timestamp with an explicit timezone."
        ) from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest")
    ingest.add_argument("--input", required=True, type=Path)
    ingest.add_argument("--inventory", required=True, type=Path)
    ingest.add_argument("--at", required=True, type=audit_time)

    show = commands.add_parser("show")
    show.add_argument("--case-id", required=True)

    transition = commands.add_parser("transition")
    transition.add_argument("--case-id", required=True)
    transition.add_argument("--expected-state", required=True)
    transition.add_argument("--to", required=True)
    transition.add_argument("--operator", required=True)
    transition.add_argument("--reason", required=True)
    transition.add_argument("--at", required=True, type=audit_time)
    args = parser.parse_args(argv)

    try:
        if args.db.is_symlink():
            raise ValueError("Database must not be a symbolic link.")

        if args.command == "ingest":
            paths = [args.db.resolve(), args.input.resolve(), args.inventory.resolve()]
            if len(set(paths)) != len(paths):
                raise ValueError("Database and input files must differ.")
            inventory = load_inventory(args.inventory)
            with args.input.open("rb") as source:
                raw = source.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Input exceeds the byte limit.")
            lines = raw.decode("utf-8").splitlines()
            if not 1 <= len(lines) <= 1_000:
                raise ValueError("Invalid alert count.")
            alerts = tuple(parse_alert(line) for line in lines)

            records = []
            with CaseStore(args.db) as store:
                for number, alert in enumerate(alerts, 1):
                    result = store.ingest(alert, now=args.at)
                    records.append(
                        {
                            "line_number": number,
                            **asdict(result),
                            "asset_context": lookup_asset(inventory, alert.hostname),
                            "case": store.get_case(result.case_id),
                        }
                    )
            report = {
                "schema_version": 1,
                "analysis_status": "complete",
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "audit_time": args.at.isoformat(),
                "summary": dict(Counter(record["status"] for record in records)),
                "records": records,
                "limitations": [
                    "Each alert has its own transaction; batch import is not atomic.",
                    "Database commits are not rolled back on report-output failure.",
                    "Asset context is a report-time synthetic lookup.",
                ],
            }
            exit_code = (
                1 if any(record["status"] == "conflict" for record in records) else 0
            )
        else:
            if not args.db.is_file():
                raise ValueError("Existing database required.")
            with CaseStore(args.db) as store:
                if args.command == "show":
                    report = store.get_case(args.case_id)
                else:
                    report = transition_case(
                        store,
                        case_id=args.case_id,
                        expected_state=args.expected_state,
                        target_state=args.to,
                        operator=args.operator,
                        reason=args.reason,
                        now=args.at,
                    )
            exit_code = 0

        print(json.dumps(report, indent=2, allow_nan=False))
        return exit_code

    except (OSError, ValueError, sqlite3.Error) as exc:
        print(
            f"Operation failed ({type(exc).__name__}). "
            "Previously committed database changes may remain.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
