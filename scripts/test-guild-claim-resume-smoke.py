from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
PROTOTYPE = WORKSPACE / "_runtime" / "flock" / "worker_team_prototype.py"

# Keep worker_team_prototype in CLI-only mode; these tests do not need Flock runtime/provider imports.
sys.argv = [str(PROTOTYPE), "claim-next"]
spec = importlib.util.spec_from_file_location("worker_team_prototype", PROTOTYPE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _db_path() -> Path:
    return Path(tempfile.mkdtemp(prefix="hermes-claim-resume-")) / "worker-team.sqlite"


def _task(task_id: str, *, status: str = "open", assignee_id: str | None = None, lease_until: str | None = None, depends_on: list[str] | None = None) -> mod.GuildTask:
    return mod.GuildTask(
        task_id=task_id,
        task_type="execution" if not task_id.endswith("review") else "join_review",
        required_rank="C",
        required_skill="implementation" if not task_id.endswith("review") else "review",
        owner_area="smoke",
        status=status,
        plan_review_required=False,
        plan_review_status="not_required",
        quest_chain_id="quest-claim-resume-smoke",
        sequence_no=1,
        depends_on=depends_on or [],
        output_artifact="smoke_artifact",
        title=task_id,
        request="claim resume smoke",
    )


def _save(db: Path, task: mod.GuildTask, *, assignee_id: str | None = None, lease_until: str | None = None) -> None:
    mod.save_task_record(db, task)
    if assignee_id is not None or lease_until is not None:
        with mod.connect_task_db(db) as con:
            con.execute(
                f"update {mod.TASK_TABLE} set assignee_id=?, claimed_at=?, lease_until=?, heartbeat_at=? where task_id=?",
                (assignee_id, mod.now_iso(), lease_until, mod.now_iso(), task.task_id),
            )
            con.commit()


def _claim(db: Path, agent_id: str, *, skills: str = "implementation", task_id: str | None = None) -> dict:
    return mod.claim_next_task(
        db,
        argparse.Namespace(
            agent_id=agent_id,
            agent_rank="C",
            skills=skills,
            task_id=task_id,
            quest_chain_id="quest-claim-resume-smoke",
            lease_seconds=900,
            scan_limit=50,
            min_open_age_seconds=0,
        ),
    )


def _release_expired(db: Path) -> dict:
    return mod.release_expired_claims(db, argparse.Namespace(limit=50))


def _unlock(db: Path) -> dict:
    return mod.unlock_ready_tasks(db, argparse.Namespace(limit=50))


def _status(db: Path, task_id: str) -> str:
    with mod.connect_task_db(db) as con:
        return con.execute(f"select status from {mod.TASK_TABLE} where task_id=?", (task_id,)).fetchone()["status"]


def test_claimed_task_assigned_to_same_agent_can_resume() -> None:
    db = _db_path()
    lease = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(timespec="seconds")
    _save(db, _task("task-same-agent", status="claimed"), assignee_id="worker-c", lease_until=lease)

    result = _claim(db, "worker-c", task_id="task-same-agent")

    assert result["claimed"] is True, result
    assert result.get("resumed") is True, result
    assert result["task"]["task_id"] == "task-same-agent"
    assert _status(db, "task-same-agent") == "claimed"


def test_claimed_task_assigned_to_other_agent_is_not_claimed() -> None:
    db = _db_path()
    lease = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(timespec="seconds")
    _save(db, _task("task-other-agent", status="claimed"), assignee_id="worker-c", lease_until=lease)

    result = _claim(db, "worker-a", task_id="task-other-agent")

    assert result["claimed"] is False, result
    assert _status(db, "task-other-agent") == "claimed"


def test_expired_claimed_task_can_be_released_and_later_claimed_normally() -> None:
    db = _db_path()
    expired = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(timespec="seconds")
    _save(db, _task("task-expired", status="claimed"), assignee_id="worker-c", lease_until=expired)

    release = _release_expired(db)
    result = _claim(db, "worker-a", task_id="task-expired")

    assert release["released_count"] == 1, release
    assert result["claimed"] is True, result
    assert result.get("resumed") in (False, None), result
    assert result["task"]["task_id"] == "task-expired"


def test_review_stays_blocked_until_dependency_task_is_done() -> None:
    db = _db_path()
    _save(db, _task("task-dep", status="claimed"), assignee_id="worker-c", lease_until=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(timespec="seconds"))
    review = _task("task-review", status="blocked", depends_on=["task-dep"])
    _save(db, review)

    blocked = _unlock(db)
    assert blocked["unlocked_count"] == 0, blocked
    assert _status(db, "task-review") == "blocked"

    with mod.connect_task_db(db) as con:
        task = _task("task-dep", status="done")
        mod.save_task_record_in_connection(con, task)
        con.commit()

    unlocked = _unlock(db)
    assert unlocked["unlocked_count"] == 1, unlocked
    assert _status(db, "task-review") == "open"


if __name__ == "__main__":
    tests = [
        test_claimed_task_assigned_to_same_agent_can_resume,
        test_claimed_task_assigned_to_other_agent_is_not_claimed,
        test_expired_claimed_task_can_be_released_and_later_claimed_normally,
        test_review_stays_blocked_until_dependency_task_is_done,
    ]
    for test in tests:
        test()
    print("ok: guild claim resume smoke")
