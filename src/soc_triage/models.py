"""Immutable validated SOC alerts with explicit source identity."""

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timezone

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"})
CATEGORIES = frozenset({"authentication", "network", "endpoint"})


def validate_identifier(value: str) -> None:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid bounded identifier.")


@dataclass(frozen=True)
class Alert:
    source_namespace: str
    source_alert_id: str
    occurred_at: datetime
    category: str
    severity: str
    hostname: str
    source_ip: str | None
    evidence_refs: tuple[str, ...]

    def __post_init__(self):
        for value in (self.source_namespace, self.source_alert_id, self.hostname):
            validate_identifier(value)
        if (
            not isinstance(self.occurred_at, datetime)
            or self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() is None
        ):
            raise ValueError("Occurrence timestamp must be timezone-aware.")
        object.__setattr__(
            self, "occurred_at", self.occurred_at.astimezone(timezone.utc)
        )
        if not isinstance(self.category, str) or self.category not in CATEGORIES:
            raise ValueError("Unsupported alert category.")
        if not isinstance(self.severity, str) or self.severity not in SEVERITIES:
            raise ValueError("Unsupported severity.")
        if self.source_ip is not None:
            if not isinstance(self.source_ip, str) or "%" in self.source_ip:
                raise ValueError("Invalid source IP.")
            object.__setattr__(
                self, "source_ip", str(ipaddress.ip_address(self.source_ip))
            )
        if (
            type(self.evidence_refs) is not tuple
            or not 1 <= len(self.evidence_refs) <= 20
        ):
            raise ValueError("Evidence must contain 1-20 immutable references.")
        for reference in self.evidence_refs:
            if (
                not isinstance(reference, str)
                or not reference.strip()
                or reference != reference.strip()
                or len(reference) > 256
                or any(ord(character) < 32 for character in reference)
            ):
                raise ValueError("Invalid evidence reference.")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("Duplicate evidence reference.")
        # References form an unordered evidence set in this schema.
        object.__setattr__(self, "evidence_refs", tuple(sorted(self.evidence_refs)))

    @property
    def identity(self) -> tuple[str, str]:
        return self.source_namespace, self.source_alert_id
