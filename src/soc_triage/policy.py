"""Explicit deterministic laboratory triage policy."""

from dataclasses import dataclass

from soc_triage.models import Alert

PRIORITY_BY_SEVERITY = {
    "CRITICAL": "P1",
    "HIGH": "P2",
    "UNKNOWN": "P2",
    "MEDIUM": "P3",
    "LOW": "P4",
}


@dataclass(frozen=True)
class TriageDecision:
    priority: str
    rationale: str
    policy_version: str


def triage_alert(alert: Alert) -> TriageDecision:
    if not isinstance(alert, Alert):
        raise ValueError("A validated alert is required.")
    return TriageDecision(
        priority=PRIORITY_BY_SEVERITY[alert.severity],
        rationale=f"Laboratory severity mapping: {alert.severity}.",
        policy_version="severity-baseline-v1",
    )
