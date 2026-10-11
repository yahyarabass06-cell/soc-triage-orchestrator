"""Explicit case transitions with transactional audit recording."""

from datetime import datetime, timezone

from soc_triage.models import validate_identifier
from soc_triage.storage import CaseStore

ALLOWED_TRANSITIONS = {
    "new": frozenset({"investigating"}),
    "investigating": frozenset({"closed"}),
    "closed": frozenset(),
}


def transition_case(
    store: CaseStore,
    *,
    case_id: str,
    expected_state: str,
    target_state: str,
    operator: str,
    reason: str,
    now: datetime,
) -> dict:
    if not isinstance(store, CaseStore):
        raise ValueError("A case store is required.")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("A case identifier is required.")
    validate_identifier(operator)
    if (
        not isinstance(reason, str)
        or not reason.strip()
        or reason != reason.strip()
        or len(reason) > 1_000
        or any(ord(character) < 32 for character in reason)
    ):
        raise ValueError("A bounded single-line transition reason is required.")
    if (
        not isinstance(expected_state, str)
        or expected_state not in ALLOWED_TRANSITIONS
        or not isinstance(target_state, str)
        or target_state not in ALLOWED_TRANSITIONS
    ):
        raise ValueError("Unknown workflow state.")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Audit clock must be timezone-aware.")
    normalized_now = now.astimezone(timezone.utc)

    connection = store.connection
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute(
            "SELECT state FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Unknown case.")
        if row["state"] != expected_state:
            raise ValueError("Case state differs from the expected state.")
        if target_state not in ALLOWED_TRANSITIONS[expected_state]:
            raise ValueError("Transition is not allowed.")

        latest = connection.execute(
            """
            SELECT recorded_at FROM audit
            WHERE case_id = ? ORDER BY audit_id DESC LIMIT 1
            """,
            (case_id,),
        ).fetchone()
        if latest is None:
            raise ValueError("Case audit history is missing.")
        if normalized_now < datetime.fromisoformat(latest["recorded_at"]):
            raise ValueError("Audit clock precedes the previous entry.")

        connection.execute(
            "UPDATE cases SET state = ? WHERE case_id = ?",
            (target_state, case_id),
        )
        connection.execute(
            """
            INSERT INTO audit(
                case_id, recorded_at, operator, from_state, to_state, reason
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                normalized_now.isoformat(),
                operator,
                expected_state,
                target_state,
                reason,
            ),
        )
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise

    return store.get_case(case_id)
