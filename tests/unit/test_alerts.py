"""Verify identity stability and content-sensitive fingerprints."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from soc_triage.models import Alert
from soc_triage.parsing import parse_alert
from soc_triage.serialization import alert_fields, alert_fingerprint


@pytest.fixture
def alert():
    return Alert(
        source_namespace="lab-auth",
        source_alert_id="alert-001",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        category="authentication",
        severity="HIGH",
        hostname="lab-server",
        source_ip="192.0.2.10",
        evidence_refs=("synthetic-auth:2", "synthetic-auth:1"),
    )


def test_round_trip_preserves_identity_and_fingerprint(alert):
    parsed = parse_alert(json.dumps(alert_fields(alert)))
    assert parsed == alert
    assert parsed.identity == ("lab-auth", "alert-001")
    assert alert_fingerprint(parsed) == alert_fingerprint(alert)


def test_changed_content_keeps_identity_but_changes_fingerprint(alert):
    changed = replace(alert, severity="CRITICAL")
    assert changed.identity == alert.identity
    assert alert_fingerprint(changed) != alert_fingerprint(alert)


def test_namespace_is_part_of_identity(alert):
    changed = replace(alert, source_namespace="other-source")
    assert changed.identity != alert.identity


def test_equivalent_timezone_and_evidence_order_are_normalized(alert):
    changed = replace(
        alert,
        occurred_at=alert.occurred_at.astimezone(timezone(timedelta(hours=2))),
        evidence_refs=tuple(reversed(alert.evidence_refs)),
    )
    assert alert_fingerprint(changed) == alert_fingerprint(alert)


def test_equivalent_ipv6_representations_are_normalized(alert):
    first = replace(alert, source_ip="2001:db8::1")
    second = replace(alert, source_ip="2001:0db8:0:0:0:0:0:1")
    assert alert_fingerprint(first) == alert_fingerprint(second)


def test_alert_is_immutable(alert):
    with pytest.raises(FrozenInstanceError):
        alert.severity = "LOW"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_namespace", ""),
        ("source_alert_id", "../alert"),
        ("occurred_at", datetime(2026, 1, 1)),
        ("category", "unsupported"),
        ("severity", "URGENT"),
        ("hostname", " host"),
        ("source_ip", "not-an-ip"),
        ("source_ip", "fe80::1%eth0"),
        ("evidence_refs", []),
        ("evidence_refs", ()),
        ("evidence_refs", ("same", "same")),
        ("evidence_refs", ("line\nbreak",)),
    ],
)
def test_invalid_alert_is_rejected(alert, field, value):
    with pytest.raises(ValueError):
        replace(alert, **{field: value})


@pytest.mark.parametrize(
    "text",
    [
        "{",
        '{"schema_version": 1, "schema_version": 1}',
        '{"schema_version": NaN}',
        "[]",
    ],
)
def test_invalid_json_is_rejected(text):
    with pytest.raises(ValueError):
        parse_alert(text)


def test_unknown_field_is_rejected(alert):
    data = alert_fields(alert)
    data["run_command"] = "unused"
    with pytest.raises(ValueError):
        parse_alert(json.dumps(data))
