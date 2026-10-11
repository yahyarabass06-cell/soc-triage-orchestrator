"""Transactional alert ingestion and persistent investigation cases."""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from soc_triage.models import Alert
from soc_triage.policy import triage_alert
from soc_triage.serialization import alert_fingerprint, canonical_json


@dataclass(frozen=True)
class IngestionResult:
    status: str
    case_id: str


class CaseStore:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(str(path), timeout=5, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id INTEGER PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    UNIQUE(namespace, source_id)
                );
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    alert_id INTEGER NOT NULL UNIQUE
                        REFERENCES alerts(alert_id),
                    state TEXT NOT NULL
                        CHECK(state IN ('new', 'investigating', 'closed')),
                    priority TEXT NOT NULL
                        CHECK(priority IN ('P1', 'P2', 'P3', 'P4')),
                    rationale TEXT NOT NULL,
                    policy_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    audit_id INTEGER PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(case_id),
                    recorded_at TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    reason TEXT NOT NULL
                );
                """
            )
        except sqlite3.Error:
            self.connection.close()
            raise

    def ingest(self, alert: Alert, *, now: datetime) -> IngestionResult:
        if not isinstance(alert, Alert):
            raise ValueError("A validated alert is required.")
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError("Audit clock must be timezone-aware.")

        fingerprint = alert_fingerprint(alert)
        decision = triage_alert(alert)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self.connection.execute(
                """
                SELECT alerts.fingerprint, cases.case_id
                FROM alerts JOIN cases USING(alert_id)
                WHERE namespace = ? AND source_id = ?
                """,
                alert.identity,
            ).fetchone()
            if existing is not None:
                self.connection.execute("ROLLBACK")
                status = (
                    "duplicate"
                    if existing["fingerprint"] == fingerprint
                    else "conflict"
                )
                return IngestionResult(status, existing["case_id"])

            cursor = self.connection.execute(
                """
                INSERT INTO alerts(namespace, source_id, fingerprint, content_json)
                VALUES (?, ?, ?, ?)
                """,
                (*alert.identity, fingerprint, canonical_json(alert)),
            )
            case_id = str(uuid.uuid4())
            self.connection.execute(
                """
                INSERT INTO cases(
                    case_id, alert_id, state, priority, rationale, policy_version
                ) VALUES (?, ?, 'new', ?, ?, ?)
                """,
                (
                    case_id,
                    cursor.lastrowid,
                    decision.priority,
                    decision.rationale,
                    decision.policy_version,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO audit(
                    case_id, recorded_at, operator, from_state, to_state, reason
                ) VALUES (?, ?, 'system', NULL, 'new', 'Validated alert ingested')
                """,
                (case_id, now.astimezone(timezone.utc).isoformat()),
            )
            self.connection.execute("COMMIT")
            return IngestionResult("created", case_id)
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            raise

    def get_case(self, case_id: str) -> dict:
        if not isinstance(case_id, str):
            raise ValueError("Case identifier must be a string.")
        row = self.connection.execute(
            """
            SELECT cases.*, alerts.content_json, alerts.fingerprint
            FROM cases JOIN alerts USING(alert_id)
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown case.")
        result = dict(row)
        result["alert"] = json.loads(result.pop("content_json"))
        result["audit"] = [
            dict(entry)
            for entry in self.connection.execute(
                "SELECT * FROM audit WHERE case_id = ? ORDER BY audit_id",
                (case_id,),
            )
        ]
        return result

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
