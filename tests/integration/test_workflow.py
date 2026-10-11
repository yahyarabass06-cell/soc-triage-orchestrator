"""Verify transitions, stale commands and transactional audit failures."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from soc_triage.models import Alert
from soc_triage.storage import CaseStore
from soc_triage.workflow import transition_case

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def case_store(tmp_path):
    with CaseStore(tmp_path / "state.sqlite") as store:
        alert = Alert(
            source_namespace="lab-auth",
            source_alert_id="alert-001",
            occurred_at=NOW,
            category="authentication",
            severity="HIGH",
            hostname="lab-server",
            source_ip=None,
            evidence_refs=("synthetic:1",),
        )
        result = store.ingest(alert, now=NOW)
        yield store, result.case_id


def change(store, case_id, expected="new", target="investigating", **extra):
    arguments = {
        "case_id": case_id,
        "expected_state": expected,
        "target_state": target,
        "operator": "student-analyst",
        "reason": "Review synthetic evidence.",
        "now": NOW + timedelta(seconds=1),
    }
    arguments.update(extra)
    return transition_case(store, **arguments)


def test_complete_workflow_preserves_history(case_store):
    store, case_id = case_store
    change(store, case_id)
    result = change(
        store,
        case_id,
        "investigating",
        "closed",
        now=NOW + timedelta(seconds=2),
        reason="Synthetic investigation completed.",
    )
    assert result["state"] == "closed"
    assert [entry["to_state"] for entry in result["audit"]] == [
        "new",
        "investigating",
        "closed",
    ]
    assert result["audit"][-1]["operator"] == "student-analyst"


def test_direct_closure_is_rejected_without_mutation(case_store):
    store, case_id = case_store
    with pytest.raises(ValueError, match="not allowed"):
        change(store, case_id, target="closed")
    result = store.get_case(case_id)
    assert result["state"] == "new"
    assert len(result["audit"]) == 1


def test_stale_expected_state_is_rejected(case_store):
    store, case_id = case_store
    change(store, case_id)
    with pytest.raises(ValueError, match="expected"):
        change(store, case_id)
    assert len(store.get_case(case_id)["audit"]) == 2


def test_audit_failure_rolls_back_state_change(case_store):
    store, case_id = case_store
    store.connection.execute(
        """
        CREATE TEMP TRIGGER fail_transition_audit
        BEFORE INSERT ON audit
        BEGIN SELECT RAISE(ABORT, 'Synthetic audit failure'); END;
        """
    )
    with pytest.raises(sqlite3.Error):
        change(store, case_id)
    assert store.get_case(case_id)["state"] == "new"
    assert len(store.get_case(case_id)["audit"]) == 1


@pytest.mark.parametrize(
    "extra",
    [
        {"reason": ""},
        {"operator": " invalid"},
        {"now": NOW - timedelta(seconds=1)},
    ],
)
def test_invalid_transition_metadata_is_rejected(case_store, extra):
    store, case_id = case_store
    with pytest.raises(ValueError):
        change(store, case_id, **extra)
    assert store.get_case(case_id)["state"] == "new"
