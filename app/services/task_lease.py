"""SQLite-backed task leases for multi-worker idempotency.

A lease is a short, renewable ownership record for (task_type, entity_id).
Claims run inside BEGIN IMMEDIATE so two processes cannot both win the same
entity. Expired leases are reclaimable after a worker crash.
"""

import time
import uuid

from database import get_db

DEFAULT_LEASE_SECONDS = 15 * 60


def new_owner_id(prefix: str = "worker") -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def claim_task(
    task_type: str,
    entity_id: int,
    owner: str,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: int | None = None,
) -> bool:
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    current = int(time.time()) if now is None else int(now)
    lease_until = current + lease_seconds
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM task_leases WHERE task_type = ? AND entity_id = ? AND lease_until <= ?",
            (task_type, entity_id, current),
        )
        cursor = conn.execute(
            """INSERT OR IGNORE INTO task_leases(task_type, entity_id, owner, lease_until)
               VALUES (?, ?, ?, ?)""",
            (task_type, entity_id, owner, lease_until),
        )
        claimed = cursor.rowcount == 1
        conn.commit()
        return claimed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def release_task(task_type: str, entity_id: int, owner: str) -> bool:
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM task_leases WHERE task_type = ? AND entity_id = ? AND owner = ?",
            (task_type, entity_id, owner),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def renew_task(
    task_type: str,
    entity_id: int,
    owner: str,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: int | None = None,
) -> bool:
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    current = int(time.time()) if now is None else int(now)
    conn = get_db()
    try:
        cursor = conn.execute(
            """UPDATE task_leases
               SET lease_until = ?
               WHERE task_type = ? AND entity_id = ? AND owner = ? AND lease_until > ?""",
            (current + lease_seconds, task_type, entity_id, owner, current),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()
