"""Strict bounded parsing of supported SOC alert records."""

import json
from datetime import datetime

from soc_triage.models import Alert

MAX_ALERT_CHARACTERS = 16_384


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON value.")


def parse_alert(text: str) -> Alert:
    if (
        not isinstance(text, str)
        or not text.strip()
        or len(text) > MAX_ALERT_CHARACTERS
    ):
        raise ValueError("Alert is empty or exceeds the character limit.")
    data = json.loads(
        text,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )
    expected = {
        "schema_version",
        "source_namespace",
        "source_alert_id",
        "occurred_at",
        "category",
        "severity",
        "hostname",
        "source_ip",
        "evidence_refs",
    }
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError("Unexpected alert fields.")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported alert schema.")
    if not isinstance(data["occurred_at"], str):
        raise ValueError("Occurrence timestamp must be a string.")
    if not isinstance(data["evidence_refs"], list):
        raise ValueError("Evidence references must be a list.")

    return Alert(
        source_namespace=data["source_namespace"],
        source_alert_id=data["source_alert_id"],
        occurred_at=datetime.fromisoformat(data["occurred_at"]),
        category=data["category"],
        severity=data["severity"],
        hostname=data["hostname"],
        source_ip=data["source_ip"],
        evidence_refs=tuple(data["evidence_refs"]),
    )
