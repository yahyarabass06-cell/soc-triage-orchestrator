"""Stable laboratory serialization for alert conflict detection."""

import hashlib
import json

from soc_triage.models import Alert


def alert_fields(alert: Alert) -> dict:
    if not isinstance(alert, Alert):
        raise ValueError("A validated alert is required.")
    return {
        "schema_version": 1,
        "source_namespace": alert.source_namespace,
        "source_alert_id": alert.source_alert_id,
        "occurred_at": alert.occurred_at.isoformat(timespec="microseconds"),
        "category": alert.category,
        "severity": alert.severity,
        "hostname": alert.hostname,
        "source_ip": alert.source_ip,
        "evidence_refs": list(alert.evidence_refs),
    }


def canonical_json(alert: Alert) -> str:
    return json.dumps(
        alert_fields(alert),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def alert_fingerprint(alert: Alert) -> str:
    return hashlib.sha256(canonical_json(alert).encode("ascii")).hexdigest()
