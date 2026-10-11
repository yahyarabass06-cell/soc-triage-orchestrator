"""Exercise persistent ingestion and audited transitions through the CLI."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_cli(database, *arguments):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "soc_triage.cli",
            "--db",
            str(database),
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def ingest(database):
    return run_cli(
        database,
        "ingest",
        "--input",
        str(ROOT / "data/synthetic/alerts-demo.jsonl"),
        "--inventory",
        str(ROOT / "config/assets-demo.json"),
        "--at",
        "2026-01-01T00:00:00+00:00",
    )


def test_ingestion_restart_and_transition(tmp_path):
    database = tmp_path / "cases.sqlite"
    first = ingest(database)
    assert first.returncode == 1
    report = json.loads(first.stdout)
    assert report["summary"] == {"created": 2, "duplicate": 1, "conflict": 1}
    assert report["records"][0]["asset_context"]["status"] == "found"
    case_id = report["records"][0]["case_id"]

    second = ingest(database)
    assert second.returncode == 1
    assert json.loads(second.stdout)["summary"] == {"duplicate": 3, "conflict": 1}

    changed = run_cli(
        database,
        "transition",
        "--case-id",
        case_id,
        "--expected-state",
        "new",
        "--to",
        "investigating",
        "--operator",
        "student-analyst",
        "--reason",
        "Inspect synthetic evidence.",
        "--at",
        "2026-01-01T00:00:01+00:00",
    )
    assert changed.returncode == 0
    assert json.loads(changed.stdout)["state"] == "investigating"

    shown = run_cli(database, "show", "--case-id", case_id)
    assert shown.returncode == 0
    assert len(json.loads(shown.stdout)["audit"]) == 2


def test_missing_database_is_not_created_by_show(tmp_path):
    database = tmp_path / "missing.sqlite"
    result = run_cli(database, "show", "--case-id", "missing")
    assert result.returncode == 2
    assert result.stdout == ""
    assert not database.exists()
