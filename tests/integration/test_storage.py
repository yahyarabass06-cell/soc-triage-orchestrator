"""Verify atomic creation, conflict preservation and restart behavior."""

import sqlite3
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from soc_triage.models import Alert
from soc_triage.storage import CaseStore

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def alert():
    return Alert(
        source_namespace="lab-auth",
        source_alert_id="alert-001",
        occurred_at=NOW,
        category="authentication",
        severity="HIGH",
        hostname="lab-server",
        source_ip="192.0.2.10",
        evidence_refs=("synthetic-auth:1",),
    )


def test_identical_import_creates_one_case_and_one_audit(tmp_path, alert):
    with CaseStore(tmp_path / "state.sqlite") as store:
        first = store.ingest(alert, now=NOW)
        repeated = store.ingest(alert, now=NOW)
        assert first.status == "created"
        assert repeated.status == "duplicate"
        assert first.case_id == repeated.case_id
        case = store.get_case(first.case_id)
        assert case["state"] == "new"
        assert case["priority"] == "P2"
        assert len(case["audit"]) == 1


def test_conflict_preserves_original_content(tmp_path, alert):
    with CaseStore(tmp_path / "state.sqlite") as store:
        first = store.ingest(alert, now=NOW)
        conflict = store.ingest(replace(alert, severity="CRITICAL"), now=NOW)
        assert conflict.status == "conflict"
        assert conflict.case_id == first.case_id
        case = store.get_case(first.case_id)
        assert case["alert"]["severity"] == "HIGH"
        assert case["priority"] == "P2"
        assert len(case["audit"]) == 1


def test_idempotence_survives_restart(tmp_path, alert):
    path = tmp_path / "state.sqlite"
    with CaseStore(path) as store:
        first = store.ingest(alert, now=NOW)
    with CaseStore(path) as store:
        repeated = store.ingest(alert, now=NOW)
        assert repeated.status == "duplicate"
        assert repeated.case_id == first.case_id


def test_audit_failure_rolls_back_alert_and_case(tmp_path, alert):
    with CaseStore(tmp_path / "state.sqlite") as store:
        store.connection.execute(
            """
            CREATE TEMP TRIGGER fail_audit
            BEFORE INSERT ON audit
            BEGIN SELECT RAISE(ABORT, 'Synthetic audit failure'); END;
            """
        )
        with pytest.raises(sqlite3.Error):
            store.ingest(alert, now=NOW)

        for table in ("alerts", "cases", "audit"):
            count = store.connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            assert count == 0


def test_distinct_namespace_creates_distinct_case(tmp_path, alert):
    with CaseStore(tmp_path / "state.sqlite") as store:
        first = store.ingest(alert, now=NOW)
        second = store.ingest(replace(alert, source_namespace="other-source"), now=NOW)
        assert second.status == "created"
        assert second.case_id != first.case_id
