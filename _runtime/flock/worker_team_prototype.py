from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, Field


FLOCK_SOURCE = Path(__file__).resolve().parents[1] / "research" / "flock" / "src"
if FLOCK_SOURCE.exists():
    sys.path.insert(0, str(FLOCK_SOURCE))

DEFAULT_DB_PATH = (
    Path.home()
    / "AppData"
    / "Local"
    / "hermes"
    / "flock"
    / "worker_team.sqlite"
)

CLI_ONLY_COMMANDS = {
    "create-task",
    "list-tasks",
    "inspect-task",
    "set-status",
    "unlock-ready",
    "claim-next",
    "heartbeat",
    "release-expired",
    "publish-artifact",
    "list-artifacts",
    "run-join-review",
    "run-fake-worker",
    "seed-demo-chain",
    "dashboard",
}


def should_load_flock_runtime(argv: list[str]) -> bool:
    if any(arg in {"-h", "--help"} for arg in argv[1:]):
        return False
    return not any(arg in CLI_ONLY_COMMANDS for arg in argv[1:])


if should_load_flock_runtime(sys.argv):
    from flock import Flock, flock_type
    from flock.components import EngineComponent
    from flock.core.store import InMemoryBlackboardStore, SQLiteBlackboardStore
    from flock.core.subscription import JoinSpec
    from flock.utils.runtime import EvalInputs, EvalResult
else:
    # Durable queue/dashboard commands only need Pydantic + SQLite. Avoid Flock's
    # provider import side effects so short CLI reads exit cleanly.
    def flock_type(model_class):
        return model_class

    class EngineComponent:
        pass


TASK_TABLE = "guild_tasks"
ARTIFACT_TABLE = "guild_artifacts"
RANK_ORDER = {"D": 1, "C": 2, "B": 3, "A": 4, "S": 5}
RETRYABLE_BLOCKED_REASONS = {
    "adapter_not_implemented",
    "provider_error_event",
    "provider_exhausted",
    "provider_failed",
    "provider_missing",
    "provider_timeout",
}


@flock_type
class GuildTask(BaseModel):
    task_id: str
    task_type: str = Field(
        default="execution",
        pattern="^(contract|execution|join_review|fix|final_review)$",
    )
    required_rank: str = Field(default="C", pattern="^(S|A|B|C|D)$")
    required_skill: str = "general"
    owner_area: str = "general"
    status: str = Field(default="blocked", pattern="^(blocked|open|claimed|running|review|done|failed|cancelled)$")
    plan_review_required: bool = True
    plan_review_status: str = Field(
        default="pending",
        pattern="^(not_required|pending|approved|rejected)$",
    )
    human_approval_required: bool = False
    blocked_reason: str | None = None
    quest_chain_id: str | None = None
    sequence_no: int = 0
    depends_on: list[str] = Field(default_factory=list)
    linked_tasks: list[str] = Field(default_factory=list)
    input_artifacts: list[str] = Field(default_factory=list)
    output_artifact: str = "worker_result"
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    generated_from: str | None = None
    source_artifact: str | None = None
    max_generated_tasks: int = 0
    max_fix_rounds: int = 3
    fix_round: int = 0
    max_spawned_tasks_per_join: int = 5
    max_spawned_tasks_per_chain: int = 20
    human_approval_after_failed_rounds: int = 2
    budget_token_limit: int | None = None
    title: str
    request: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    definition_of_done: list[str] = Field(default_factory=list)
    test_command: str | None = None
    style_guide: str | None = None
    evidence_required: list[str] = Field(
        default_factory=lambda: [
            "artifact",
            "summary",
            "files_changed",
            "commands_run",
            "test_result",
            "known_risks",
        ]
    )


@flock_type
class ImplementationResult(BaseModel):
    task_id: str
    quest_chain_id: str | None = None
    task_type: str
    output_artifact: str
    worker: str
    summary: str
    changed_paths: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    test_result: str = "not_run"
    known_risks: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@flock_type
class TestResult(BaseModel):
    task_id: str
    quest_chain_id: str | None = None
    task_type: str
    output_artifact: str
    worker: str
    passed: bool
    checks: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


@flock_type
class ReviewResult(BaseModel):
    task_id: str
    quest_chain_id: str | None = None
    task_type: str
    output_artifact: str
    worker: str
    approved: bool
    findings: list[str] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)
    evidence_complete: bool = False
    plan_gate_checked: bool = False


@flock_type
class TaskDecision(BaseModel):
    task_id: str
    quest_chain_id: str | None = None
    task_type: str = "join_review"
    output_artifact: str
    decision: str = Field(pattern="^(accept|revise)$")
    summary: str
    required_next_actions: list[str] = Field(default_factory=list)
    evidence: dict[str, str | bool | list[str]]
    generated_tasks: list[GuildTask] = Field(default_factory=list)
    stop_condition: str = "none"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def iso_after(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(
        timespec="seconds"
    )


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def connect_task_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("pragma journal_mode=wal")
    con.execute("pragma synchronous=normal")
    return con


def ensure_task_schema(con: sqlite3.Connection) -> None:
    con.execute(
        f"""
        create table if not exists {TASK_TABLE} (
            task_id text primary key,
            task_type text not null,
            status text not null,
            required_rank text not null,
            required_skill text not null,
            owner_area text not null,
            quest_chain_id text,
            sequence_no integer not null,
            plan_review_status text not null,
            output_artifact text not null,
            title text not null,
            assignee_id text,
            claimed_at text,
            lease_until text,
            claim_attempt integer not null default 0,
            heartbeat_at text,
            created_at text not null,
            updated_at text not null,
            payload_json text not null
        )
        """
    )
    existing_columns = {
        row["name"] for row in con.execute(f"pragma table_info({TASK_TABLE})")
    }
    migrations = {
        "assignee_id": "alter table guild_tasks add column assignee_id text",
        "claimed_at": "alter table guild_tasks add column claimed_at text",
        "lease_until": "alter table guild_tasks add column lease_until text",
        "claim_attempt": "alter table guild_tasks add column claim_attempt integer not null default 0",
        "heartbeat_at": "alter table guild_tasks add column heartbeat_at text",
    }
    for column, sql in migrations.items():
        if column not in existing_columns:
            con.execute(sql)
    con.execute(
        f"create index if not exists idx_{TASK_TABLE}_status on {TASK_TABLE}(status)"
    )
    con.execute(
        f"""
        create index if not exists idx_{TASK_TABLE}_chain
        on {TASK_TABLE}(quest_chain_id, sequence_no)
        """
    )
    con.execute(
        f"""
        create index if not exists idx_{TASK_TABLE}_claimable
        on {TASK_TABLE}(status, required_rank, required_skill, updated_at)
        """
    )
    con.execute(
        f"""
        create table if not exists {ARTIFACT_TABLE} (
            artifact_id text primary key,
            task_id text not null,
            quest_chain_id text,
            artifact_type text not null,
            producer_agent_id text not null,
            summary text not null,
            payload_json text not null,
            created_at text not null
        )
        """
    )
    con.execute(
        f"""
        create index if not exists idx_{ARTIFACT_TABLE}_task
        on {ARTIFACT_TABLE}(task_id, artifact_type, created_at)
        """
    )
    con.commit()


def save_task_record_in_connection(
    con: sqlite3.Connection, task: GuildTask, now: str | None = None
) -> None:
    now = now or now_iso()
    payload = json.dumps(task.model_dump(mode="json"), sort_keys=True)
    ensure_task_schema(con)
    existing = con.execute(
        f"select created_at from {TASK_TABLE} where task_id = ?",
        (task.task_id,),
    ).fetchone()
    created_at = existing["created_at"] if existing else now
    con.execute(
        f"""
        insert into {TASK_TABLE} (
            task_id, task_type, status, required_rank, required_skill,
            owner_area, quest_chain_id, sequence_no, plan_review_status,
            output_artifact, title, created_at, updated_at, payload_json
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(task_id) do update set
            task_type = excluded.task_type,
            status = excluded.status,
            required_rank = excluded.required_rank,
            required_skill = excluded.required_skill,
            owner_area = excluded.owner_area,
            quest_chain_id = excluded.quest_chain_id,
            sequence_no = excluded.sequence_no,
            plan_review_status = excluded.plan_review_status,
            output_artifact = excluded.output_artifact,
            title = excluded.title,
            updated_at = excluded.updated_at,
            payload_json = excluded.payload_json
        """,
        (
            task.task_id,
            task.task_type,
            task.status,
            task.required_rank,
            task.required_skill,
            task.owner_area,
            task.quest_chain_id,
            task.sequence_no,
            task.plan_review_status,
            task.output_artifact,
            task.title,
            created_at,
            now,
            payload,
        ),
    )


def save_task_record(db_path: Path, task: GuildTask) -> None:
    now = now_iso()
    with connect_task_db(db_path) as con:
        save_task_record_in_connection(con, task, now)
        con.commit()


def delete_chain_records(con: sqlite3.Connection, quest_chain_id: str) -> None:
    ensure_task_schema(con)
    con.execute(f"delete from {ARTIFACT_TABLE} where quest_chain_id = ?", (quest_chain_id,))
    con.execute(f"delete from {TASK_TABLE} where quest_chain_id = ?", (quest_chain_id,))


def demo_even_random_tasks(quest_chain_id: str) -> list[GuildTask]:
    return [
        GuildTask(
            task_id="demo-even-spec",
            task_type="contract",
            required_rank="C",
            required_skill="planning",
            owner_area="product",
            status="done",
            plan_review_required=False,
            plan_review_status="not_required",
            quest_chain_id=quest_chain_id,
            sequence_no=1,
            output_artifact="app_spec",
            title="Spec random even app",
            request="Define a simple app where clicking a button returns a positive even number under 100.",
            acceptance_criteria=[
                "button interaction is clear",
                "result is positive, even, and under 100",
            ],
            definition_of_done=["spec is accepted and execution tasks can start"],
        ),
        GuildTask(
            task_id="demo-even-app-logic",
            task_type="execution",
            required_rank="C",
            required_skill="app_logic",
            owner_area="frontend_logic",
            status="open",
            plan_review_status="approved",
            quest_chain_id=quest_chain_id,
            sequence_no=2,
            depends_on=["demo-even-spec"],
            output_artifact="app_logic_result",
            title="Build random even number logic",
            request="Create deterministic app logic that can return a positive even number below 100.",
            acceptance_criteria=["generated number is in 2..98", "generated number is even"],
            definition_of_done=["logic artifact is published"],
        ),
        GuildTask(
            task_id="demo-even-ui",
            task_type="execution",
            required_rank="C",
            required_skill="ui",
            owner_area="frontend_ui",
            status="open",
            plan_review_status="approved",
            quest_chain_id=quest_chain_id,
            sequence_no=3,
            depends_on=["demo-even-spec"],
            output_artifact="ui_result",
            title="Design simple button UI",
            request="Design a simple UI with one button and a visible result area.",
            acceptance_criteria=["button is visible", "result area is visible"],
            definition_of_done=["UI artifact is published"],
        ),
        GuildTask(
            task_id="demo-even-tester",
            task_type="execution",
            required_rank="B",
            required_skill="testing",
            owner_area="qa",
            status="blocked",
            plan_review_status="approved",
            quest_chain_id=quest_chain_id,
            sequence_no=4,
            depends_on=["demo-even-app-logic", "demo-even-ui"],
            input_artifacts=["app_logic_result", "ui_result"],
            output_artifact="test_result",
            title="Test random even app",
            request="Test that the app behavior matches the spec.",
            acceptance_criteria=["logic and UI artifacts are compatible"],
            definition_of_done=["test artifact is published"],
        ),
        GuildTask(
            task_id="demo-even-join-review",
            task_type="join_review",
            required_rank="B",
            required_skill="integration_review",
            owner_area="review",
            status="blocked",
            plan_review_status="approved",
            quest_chain_id=quest_chain_id,
            sequence_no=5,
            depends_on=["demo-even-app-logic", "demo-even-ui", "demo-even-tester"],
            input_artifacts=["app_logic_result", "ui_result", "test_result"],
            output_artifact="integration_report",
            title="Review app UI test integration",
            request="Review whether logic, UI, and test artifacts fit together.",
            acceptance_criteria=["all input artifacts are present and passing"],
            definition_of_done=["integration decision is published"],
        ),
    ]


def seed_demo_chain(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    quest_chain_id = args.quest_chain_id
    tasks = demo_even_random_tasks(quest_chain_id)
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        if args.reset:
            delete_chain_records(con, quest_chain_id)
        for task in tasks:
            save_task_record_in_connection(con, task)
        con.commit()
    return {
        "seeded": True,
        "reset": bool(args.reset),
        "db_path": str(db_path),
        "quest_chain_id": quest_chain_id,
        "task_count": len(tasks),
        "tasks": [task.task_id for task in tasks],
    }


def create_task_from_args(args: argparse.Namespace) -> GuildTask:
    request = args.request
    if getattr(args, "request_file", None):
        request = Path(args.request_file).read_text(encoding="utf-8-sig")
    if not request:
        raise ValueError("--request or --request-file is required")

    return GuildTask(
        task_id=args.task_id or f"guild-task-{uuid.uuid4().hex[:8]}",
        task_type=args.task_type,
        required_rank=args.required_rank,
        required_skill=args.required_skill,
        owner_area=args.owner_area,
        status=args.status,
        plan_review_required=not args.plan_review_not_required,
        plan_review_status=args.plan_review_status,
        human_approval_required=args.human_approval_required,
        quest_chain_id=args.quest_chain_id,
        sequence_no=args.sequence_no,
        depends_on=split_csv(args.depends_on),
        linked_tasks=split_csv(args.linked_tasks),
        input_artifacts=split_csv(args.input_artifacts),
        output_artifact=args.output_artifact,
        allowed_files=split_csv(args.allowed_files),
        forbidden_files=split_csv(args.forbidden_files),
        generated_from=args.generated_from,
        source_artifact=args.source_artifact,
        max_generated_tasks=args.max_generated_tasks,
        max_fix_rounds=args.max_fix_rounds,
        fix_round=args.fix_round,
        max_spawned_tasks_per_join=args.max_spawned_tasks_per_join,
        max_spawned_tasks_per_chain=args.max_spawned_tasks_per_chain,
        human_approval_after_failed_rounds=args.human_approval_after_failed_rounds,
        budget_token_limit=args.budget_token_limit,
        title=args.title,
        request=request,
        acceptance_criteria=args.acceptance_criteria or [],
        definition_of_done=args.definition_of_done or [],
        test_command=args.test_command,
        style_guide=args.style_guide,
    )


def create_task(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    task = create_task_from_args(args)
    save_task_record(db_path, task)
    return {
        "created": True,
        "db_path": str(db_path),
        "task": task.model_dump(mode="json"),
    }


def list_tasks(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        where = []
        params: list[object] = []
        if args.status:
            where.append("status = ?")
            params.append(args.status)
        if args.quest_chain_id:
            where.append("quest_chain_id = ?")
            params.append(args.quest_chain_id)
        where_sql = f"where {' and '.join(where)}" if where else ""
        rows = con.execute(
            f"""
            select task_id, task_type, status, required_rank, required_skill,
                   owner_area, quest_chain_id, sequence_no, plan_review_status,
                   output_artifact, title, assignee_id, lease_until,
                   claim_attempt, updated_at
            from {TASK_TABLE}
            {where_sql}
            order by coalesce(quest_chain_id, ''), sequence_no, updated_at desc
            limit ?
            """,
            (*params, args.limit),
        ).fetchall()
    return {
        "db_path": str(db_path),
        "count": len(rows),
        "tasks": [dict(row) for row in rows],
    }


def inspect_task(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        row = con.execute(
            f"select payload_json from {TASK_TABLE} where task_id = ?",
            (args.task_id,),
        ).fetchone()
    if row is None:
        return {"found": False, "db_path": str(db_path), "task_id": args.task_id}
    return {
        "found": True,
        "db_path": str(db_path),
        "task": json.loads(row["payload_json"]),
    }


def parse_payload_json(value: str | None) -> dict[str, object]:
    """Parse a JSON payload string safely.

    The worker may receive a payload file that contains a UTF‑8 BOM. The
    standard ``json.loads`` chokes on that, raising ``JSONDecodeError``.
    We strip a leading ``\ufeff`` character (the BOM) before decoding.
    """
    if not value:
        return {}
    # Remove possible UTF‑8 BOM that appears as a zero‑width non‑breaking space.
    if isinstance(value, str) and value.startswith("\ufeff"):
        value = value.lstrip("\ufeff")
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Artifact payload must be a JSON object.")
    return parsed


def publish_artifact(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    payload_json = args.payload_json
    if args.payload_json_file:
        payload_json = Path(args.payload_json_file).read_text(encoding="utf-8")
    payload = parse_payload_json(payload_json)
    artifact_id = args.artifact_id or f"artifact-{uuid.uuid4().hex[:8]}"
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        task_row = con.execute(
            f"select payload_json from {TASK_TABLE} where task_id = ?",
            (args.task_id,),
        ).fetchone()
        quest_chain_id = None
        if task_row is not None:
            task = GuildTask(**json.loads(task_row["payload_json"]))
            quest_chain_id = task.quest_chain_id
        con.execute(
            f"""
            insert into {ARTIFACT_TABLE} (
                artifact_id, task_id, quest_chain_id, artifact_type,
                producer_agent_id, summary, payload_json, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(artifact_id) do update set
                task_id = excluded.task_id,
                quest_chain_id = excluded.quest_chain_id,
                artifact_type = excluded.artifact_type,
                producer_agent_id = excluded.producer_agent_id,
                summary = excluded.summary,
                payload_json = excluded.payload_json,
                created_at = excluded.created_at
            """,
            (
                artifact_id,
                args.task_id,
                quest_chain_id,
                args.artifact_type,
                args.producer_agent_id,
                args.summary,
                json.dumps(payload, sort_keys=True),
                now_iso(),
            ),
        )
        con.commit()
    return {
        "published": True,
        "db_path": str(db_path),
        "artifact_id": artifact_id,
        "task_id": args.task_id,
        "artifact_type": args.artifact_type,
        "payload": payload,
    }


def list_artifacts(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        where = []
        params: list[object] = []
        if args.task_id:
            where.append("task_id = ?")
            params.append(args.task_id)
        if args.quest_chain_id:
            where.append("quest_chain_id = ?")
            params.append(args.quest_chain_id)
        where_sql = f"where {' and '.join(where)}" if where else ""
        rows = con.execute(
            f"""
            select artifact_id, task_id, quest_chain_id, artifact_type,
                   producer_agent_id, summary, created_at
            from {ARTIFACT_TABLE}
            {where_sql}
            order by created_at desc
            limit ?
            """,
            (*params, args.limit),
        ).fetchall()
    return {
        "db_path": str(db_path),
        "count": len(rows),
        "artifacts": [dict(row) for row in rows],
    }


def dashboard_snapshot(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        where = []
        params: list[object] = []
        if args.quest_chain_id:
            where.append("quest_chain_id = ?")
            params.append(args.quest_chain_id)
        where_sql = f"where {' and '.join(where)}" if where else ""

        task_rows = con.execute(
            f"""
            select task_id, task_type, status, required_rank, required_skill,
                   owner_area, quest_chain_id, sequence_no, plan_review_status,
                   output_artifact, title, assignee_id, claimed_at, lease_until,
                   heartbeat_at, claim_attempt, updated_at, payload_json
            from {TASK_TABLE}
            {where_sql}
            order by coalesce(quest_chain_id, ''), sequence_no, updated_at desc
            limit ?
            """,
            (*params, args.limit),
        ).fetchall()

        artifact_rows = con.execute(
            f"""
            select artifact_id, task_id, quest_chain_id, artifact_type,
                   producer_agent_id, summary, created_at
            from {ARTIFACT_TABLE}
            {where_sql}
            order by created_at desc
            limit ?
            """,
            (*params, args.artifact_limit),
        ).fetchall()

    tasks = []
    task_status_by_id = {row["task_id"]: row["status"] for row in task_rows}
    for row in task_rows:
        task = dict(row)
        payload = json.loads(str(task.pop("payload_json")))
        task["depends_on"] = payload.get("depends_on", [])
        task["human_approval_required"] = bool(payload.get("human_approval_required", False))
        task["persistent_blocked_reason"] = payload.get("blocked_reason")
        task["generated_from"] = payload.get("generated_from")
        task["fix_round"] = payload.get("fix_round", 0)
        if task["status"] == "blocked":
            if task["persistent_blocked_reason"]:
                task["block_reason"] = task["persistent_blocked_reason"]
            elif task["plan_review_status"] == "pending":
                task["block_reason"] = "plan_review_pending"
            elif task["human_approval_required"]:
                task["block_reason"] = "human_approval_required"
            else:
                waiting = [
                    f"{dep_id}:{task_status_by_id.get(dep_id, 'missing')}"
                    for dep_id in task["depends_on"]
                    if task_status_by_id.get(dep_id) != "done"
                ]
                task["block_reason"] = (
                    "waiting_dependencies:" + ",".join(waiting)
                    if waiting
                    else "blocked_unknown"
                )
        else:
            task["block_reason"] = None
        tasks.append(task)
    artifacts = [dict(row) for row in artifact_rows]
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    chains: dict[str, dict[str, object]] = {}
    for task in tasks:
        status = str(task["status"])
        task_type = str(task["task_type"])
        chain_id = str(task["quest_chain_id"] or "unassigned")
        status_counts[status] = status_counts.get(status, 0) + 1
        type_counts[task_type] = type_counts.get(task_type, 0) + 1
        chain = chains.setdefault(
            chain_id,
            {
                "quest_chain_id": chain_id,
                "task_count": 0,
                "status_counts": {},
                "next_open_tasks": [],
                "blocked_review_tasks": [],
            },
        )
        chain["task_count"] = int(chain["task_count"]) + 1
        chain_status_counts = chain["status_counts"]
        assert isinstance(chain_status_counts, dict)
        chain_status_counts[status] = chain_status_counts.get(status, 0) + 1
        if status == "open":
            next_open = chain["next_open_tasks"]
            assert isinstance(next_open, list)
            next_open.append(
                {
                    "task_id": task["task_id"],
                    "title": task["title"],
                    "required_rank": task["required_rank"],
                    "required_skill": task["required_skill"],
                }
            )
        if status == "blocked" and task["plan_review_status"] == "pending":
            blocked_review = chain["blocked_review_tasks"]
            assert isinstance(blocked_review, list)
            blocked_review.append(
                {
                    "task_id": task["task_id"],
                    "title": task["title"],
                    "task_type": task["task_type"],
                }
            )

    return {
        "db_path": str(db_path),
        "schema_version": "guild_dashboard_read_v0",
        "filters": {"quest_chain_id": args.quest_chain_id},
        "task_count": len(tasks),
        "artifact_count": len(artifacts),
        "status_counts": status_counts,
        "type_counts": type_counts,
        "chains": list(chains.values()),
        "tasks": tasks if args.include_tasks else [],
        "artifacts": artifacts if args.include_artifacts else [],
    }


def format_dashboard_text(snapshot: dict[str, object]) -> str:
    lines = [
        "Guild Dashboard",
        f"schema: {snapshot['schema_version']}",
        f"db: {snapshot['db_path']}",
        f"filters: {snapshot['filters']}",
        "",
        f"tasks: {snapshot['task_count']}  artifacts: {snapshot['artifact_count']}",
        f"status: {snapshot['status_counts']}",
        f"types: {snapshot['type_counts']}",
        "",
    ]

    chains = snapshot.get("chains", [])
    if isinstance(chains, list) and chains:
        lines.append("Chains")
        for chain in chains:
            if not isinstance(chain, dict):
                continue
            lines.append(
                f"- {chain['quest_chain_id']}: tasks={chain['task_count']} "
                f"status={chain['status_counts']}"
            )
            for task in chain.get("next_open_tasks", []):
                if isinstance(task, dict):
                    lines.append(
                        f"  open: {task['task_id']} "
                        f"[{task['required_rank']}/{task['required_skill']}] {task['title']}"
                    )
            for task in chain.get("blocked_review_tasks", []):
                if isinstance(task, dict):
                    lines.append(
                        f"  blocked plan: {task['task_id']} "
                        f"[{task['task_type']}] {task['title']}"
                    )

    tasks = snapshot.get("tasks", [])
    if isinstance(tasks, list) and tasks:
        lines.extend(["", "Tasks"])
        for task in tasks:
            if isinstance(task, dict):
                lines.append(
                    f"- {task['sequence_no']:>3} {task['task_id']} "
                    f"{task['status']}/{task['plan_review_status']} "
                    f"{task['task_type']} {task['title']}"
                )

    artifacts = snapshot.get("artifacts", [])
    if isinstance(artifacts, list) and artifacts:
        lines.extend(["", "Artifacts"])
        for artifact in artifacts:
            if isinstance(artifact, dict):
                lines.append(
                    f"- {artifact['artifact_id']} {artifact['artifact_type']} "
                    f"task={artifact['task_id']} {artifact['summary']}"
                )

    return "\n".join(lines)


def fetch_join_artifacts(
    con: sqlite3.Connection, join_task: GuildTask
) -> tuple[list[dict[str, object]], list[str]]:
    inputs = join_task.input_artifacts or join_task.depends_on
    found: list[dict[str, object]] = []
    missing: list[str] = []
    for input_id in inputs:
        rows = con.execute(
            f"""
            select artifact_id, task_id, quest_chain_id, artifact_type,
                   producer_agent_id, summary, payload_json, created_at
            from {ARTIFACT_TABLE}
            where task_id = ?
               or artifact_id = ?
               or (
                    artifact_type = ?
                    and (
                        quest_chain_id = ?
                        or ? is null
                    )
               )
            order by created_at desc
            """,
            (
                input_id,
                input_id,
                input_id,
                join_task.quest_chain_id,
                join_task.quest_chain_id,
            ),
        ).fetchall()
        if not rows:
            missing.append(input_id)
            continue
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            found.append(item)
    return found, missing


def artifact_is_ok(artifact: dict[str, object]) -> bool:
    payload = artifact.get("payload")
    if not isinstance(payload, dict):
        return False
    for key in ("ok", "passed", "approved"):
        if key in payload and payload[key] is False:
            return False
    if payload.get("status") in {"failed", "error", "mismatch"}:
        return False
    if payload.get("failures"):
        return False
    if payload.get("findings"):
        return False
    return True


def run_join_review(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        row = con.execute(
            f"select payload_json from {TASK_TABLE} where task_id = ?",
            (args.task_id,),
        ).fetchone()
        if row is None:
            return {"reviewed": False, "reason": "task_not_found", "task_id": args.task_id}

        join_task = GuildTask(**json.loads(row["payload_json"]))
        if join_task.task_type != "join_review":
            return {
                "reviewed": False,
                "reason": f"not_join_review:{join_task.task_type}",
                "task_id": join_task.task_id,
            }

        artifacts, missing = fetch_join_artifacts(con, join_task)
        if missing:
            return {
                "reviewed": False,
                "reason": "missing_input_artifacts",
                "task_id": join_task.task_id,
                "missing": missing,
                "found_count": len(artifacts),
            }

    failed = [artifact for artifact in artifacts if not artifact_is_ok(artifact)]
    accepted = not failed
    generated_tasks: list[GuildTask] = []
    stop_condition = "none"
    max_generated = min(
        join_task.max_generated_tasks or join_task.max_spawned_tasks_per_join,
        join_task.max_spawned_tasks_per_join,
    )

    if failed:
        if join_task.fix_round >= join_task.max_fix_rounds:
            stop_condition = "max_fix_rounds_reached"
        else:
            for index, artifact in enumerate(failed[:max_generated], start=1):
                task_id = f"{join_task.task_id}-fix-{index}"
                generated_tasks.append(
                    GuildTask(
                        task_id=task_id,
                        task_type="fix",
                        required_rank=join_task.required_rank,
                        required_skill=join_task.required_skill,
                        owner_area=join_task.owner_area,
                        status="blocked",
                        plan_review_required=True,
                        plan_review_status="pending",
                        human_approval_required=True,
                        quest_chain_id=join_task.quest_chain_id,
                        sequence_no=join_task.sequence_no + index,
                        depends_on=[join_task.task_id],
                        input_artifacts=[str(artifact["artifact_id"])],
                        output_artifact="fix_result",
                        generated_from=join_task.task_id,
                        source_artifact=str(artifact["artifact_id"]),
                        fix_round=join_task.fix_round + 1,
                        title=f"Fix mismatch from {artifact['task_id']}",
                        request=(
                            "Address the mismatch found by join review artifact "
                            f"{artifact['artifact_id']}."
                        ),
                        acceptance_criteria=["mismatch from join review is resolved"],
                        definition_of_done=[
                            "publish a fix artifact and pass the next join review"
                        ],
                    )
                )
            if len(failed) > max_generated:
                stop_condition = "max_generated_tasks_reached"

    decision = TaskDecision(
        task_id=join_task.task_id,
        quest_chain_id=join_task.quest_chain_id,
        task_type="join_review",
        output_artifact=join_task.output_artifact,
        decision="accept" if accepted else "revise",
        summary=(
            "Queued join review read upstream artifacts and produced an integration decision."
        ),
        required_next_actions=[] if accepted else ["review generated fix tasks"],
        evidence={
            "artifact_count": str(len(artifacts)),
            "failed_artifact_ids": [str(item["artifact_id"]) for item in failed],
            "missing_artifacts": missing,
        },
        generated_tasks=generated_tasks,
        stop_condition=stop_condition,
    )

    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        for task in generated_tasks:
            save_task_record_in_connection(con, task)
        con.execute(
            f"""
            insert into {ARTIFACT_TABLE} (
                artifact_id, task_id, quest_chain_id, artifact_type,
                producer_agent_id, summary, payload_json, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{join_task.task_id}-decision-{uuid.uuid4().hex[:8]}",
                join_task.task_id,
                join_task.quest_chain_id,
                "task_decision",
                args.reviewer_id,
                decision.summary,
                json.dumps(decision.model_dump(mode="json"), sort_keys=True),
                now_iso(),
            ),
        )
        join_task.status = "done"
        save_task_record_in_connection(con, join_task)
        con.commit()

    return {
        "reviewed": True,
        "db_path": str(db_path),
        "task_id": join_task.task_id,
        "decision": decision.model_dump(mode="json"),
    }


def update_task_status(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        row = con.execute(
            f"select payload_json from {TASK_TABLE} where task_id = ?",
            (args.task_id,),
        ).fetchone()
    if row is None:
        return {"updated": False, "reason": "task_not_found", "task_id": args.task_id}

    task = GuildTask(**json.loads(row["payload_json"]))
    task.status = args.status
    if args.status == "blocked":
        task.blocked_reason = args.blocked_reason
    else:
        task.blocked_reason = None
    save_task_record(db_path, task)
    return {
        "updated": True,
        "db_path": str(db_path),
        "task_id": task.task_id,
        "status": task.status,
    }


def dependency_statuses(con: sqlite3.Connection, task: GuildTask) -> dict[str, str | None]:
    statuses: dict[str, str | None] = {}
    for dep_id in task.depends_on:
        row = con.execute(
            f"select status from {TASK_TABLE} where task_id = ?",
            (dep_id,),
        ).fetchone()
        statuses[dep_id] = row["status"] if row else None
    return statuses


def task_unlock_reason(
    task: GuildTask, dep_statuses: dict[str, str | None]
) -> str | None:
    if task.status != "blocked":
        return "not_blocked"
    if task.blocked_reason:
        return task.blocked_reason
    if task.plan_review_required and task.plan_review_status not in {
        "approved",
        "not_required",
    }:
        return f"plan_review_{task.plan_review_status}"
    missing = [dep_id for dep_id, status in dep_statuses.items() if status is None]
    if missing:
        return f"missing_dependencies:{','.join(missing)}"
    waiting = [
        f"{dep_id}:{status}"
        for dep_id, status in dep_statuses.items()
        if status != "done"
    ]
    if waiting:
        return f"waiting_dependencies:{','.join(waiting)}"
    return None


def rank_can_claim(agent_rank: str, task_rank: str) -> bool:
    return RANK_ORDER[agent_rank] >= RANK_ORDER[task_rank]


def skill_can_claim(agent_skills: list[str], task_skill: str) -> bool:
    if task_skill == "general":
        return True
    return task_skill in agent_skills


def claim_next_task(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    agent_skills = split_csv(args.skills)
    if not agent_skills:
        agent_skills = ["general"]
    lease_until = iso_after(args.lease_seconds)
    now = now_iso()
    now_dt = datetime.now(timezone.utc)
    min_open_age_seconds = max(0, int(args.min_open_age_seconds or 0))

    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        con.execute("begin immediate")
        skipped: list[dict[str, str]] = []

        resume_where = ["status in ('claimed', 'running')", "assignee_id = ?"]
        resume_params: list[object] = [args.agent_id]
        if args.task_id:
            resume_where.append("task_id = ?")
            resume_params.append(args.task_id)
        if args.quest_chain_id:
            resume_where.append("quest_chain_id = ?")
            resume_params.append(args.quest_chain_id)
        resume_rows = con.execute(
            f"""
            select task_id, status, required_rank, required_skill, lease_until, payload_json
            from {TASK_TABLE}
            where {' and '.join(resume_where)}
            order by updated_at asc
            limit ?
            """,
            (*resume_params, args.scan_limit),
        ).fetchall()
        for row in resume_rows:
            current_lease = parse_iso(row["lease_until"])
            if current_lease is None or current_lease <= now_dt:
                skipped.append(
                    {
                        "task_id": row["task_id"],
                        "reason": "claimed_lease_expired_release_required",
                    }
                )
                continue
            task = GuildTask(**json.loads(row["payload_json"]))
            if not rank_can_claim(args.agent_rank, task.required_rank):
                skipped.append(
                    {
                        "task_id": task.task_id,
                        "reason": f"rank_too_low:{args.agent_rank}<{task.required_rank}",
                    }
                )
                continue
            if not skill_can_claim(agent_skills, task.required_skill):
                skipped.append(
                    {
                        "task_id": task.task_id,
                        "reason": f"missing_skill:{task.required_skill}",
                    }
                )
                continue
            cursor = con.execute(
                f"""
                update {TASK_TABLE}
                set lease_until = ?,
                    heartbeat_at = ?,
                    updated_at = ?
                where task_id = ?
                  and assignee_id = ?
                  and status in ('claimed', 'running')
                """,
                (lease_until, now, now, task.task_id, args.agent_id),
            )
            if cursor.rowcount != 1:
                con.rollback()
                return {
                    "claimed": False,
                    "db_path": str(db_path),
                    "agent_id": args.agent_id,
                    "task_id": args.task_id,
                    "quest_chain_id": args.quest_chain_id,
                    "reason": "lost_resume_race",
                }
            con.commit()
            task.status = row["status"]
            return {
                "claimed": True,
                "resumed": True,
                "db_path": str(db_path),
                "agent_id": args.agent_id,
                "agent_rank": args.agent_rank,
                "agent_skills": agent_skills,
                "task_id": args.task_id,
                "quest_chain_id": args.quest_chain_id,
                "lease_until": lease_until,
                "task": task.model_dump(mode="json"),
            }

        where = ["status = 'open'"]
        params: list[object] = []
        if args.task_id:
            where.append("task_id = ?")
            params.append(args.task_id)
        if args.quest_chain_id:
            where.append("quest_chain_id = ?")
            params.append(args.quest_chain_id)
        where_sql = " and ".join(where)
        rows = con.execute(
            f"""
            select rowid, task_id, required_rank, required_skill, updated_at, payload_json
            from {TASK_TABLE}
            where {where_sql}
            order by
                case required_rank
                    when 'S' then 5
                    when 'A' then 4
                    when 'B' then 3
                    when 'C' then 2
                    when 'D' then 1
                    else 0
                end desc,
                updated_at asc
            limit ?
            """,
            (*params, args.scan_limit),
        ).fetchall()

        selected: sqlite3.Row | None = None
        selected_task: GuildTask | None = None
        for row in rows:
            task = GuildTask(**json.loads(row["payload_json"]))
            if min_open_age_seconds > 0:
                opened_at = parse_iso(row["updated_at"])
                if opened_at is not None:
                    open_age = (now_dt - opened_at).total_seconds()
                    if open_age < min_open_age_seconds:
                        skipped.append(
                            {
                                "task_id": task.task_id,
                                "reason": f"open_age_too_young:{open_age:.1f}s<{min_open_age_seconds}s",
                            }
                        )
                        continue
            if not rank_can_claim(args.agent_rank, task.required_rank):
                skipped.append(
                    {
                        "task_id": task.task_id,
                        "reason": f"rank_too_low:{args.agent_rank}<{task.required_rank}",
                    }
                )
                continue
            if not skill_can_claim(agent_skills, task.required_skill):
                skipped.append(
                    {
                        "task_id": task.task_id,
                        "reason": f"missing_skill:{task.required_skill}",
                    }
                )
                continue
            selected = row
            selected_task = task
            break

        if selected is None or selected_task is None:
            con.rollback()
            return {
                "claimed": False,
                "db_path": str(db_path),
                "agent_id": args.agent_id,
                "task_id": args.task_id,
                "quest_chain_id": args.quest_chain_id,
                "skipped": skipped,
            }

        cursor = con.execute(
            f"""
            update {TASK_TABLE}
            set status = 'claimed',
                assignee_id = ?,
                claimed_at = ?,
                lease_until = ?,
                heartbeat_at = ?,
                claim_attempt = claim_attempt + 1,
                updated_at = ?
            where task_id = ? and status = 'open'
            """,
            (
                args.agent_id,
                now,
                lease_until,
                now,
                now,
                selected_task.task_id,
            ),
        )
        if cursor.rowcount != 1:
            con.rollback()
            return {
                "claimed": False,
                "db_path": str(db_path),
                "agent_id": args.agent_id,
                "task_id": args.task_id,
                "quest_chain_id": args.quest_chain_id,
                "reason": "lost_race",
            }
        con.commit()

    selected_task.status = "claimed"
    return {
        "claimed": True,
        "db_path": str(db_path),
        "agent_id": args.agent_id,
        "agent_rank": args.agent_rank,
        "agent_skills": agent_skills,
        "task_id": args.task_id,
        "quest_chain_id": args.quest_chain_id,
        "lease_until": lease_until,
        "task": selected_task.model_dump(mode="json"),
    }


def heartbeat_task(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    now = now_iso()
    lease_until = iso_after(args.lease_seconds)
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        cursor = con.execute(
            f"""
            update {TASK_TABLE}
            set lease_until = ?, heartbeat_at = ?, updated_at = ?
            where task_id = ?
              and assignee_id = ?
              and status in ('claimed', 'running')
            """,
            (lease_until, now, now, args.task_id, args.agent_id),
        )
        con.commit()
    return {
        "updated": cursor.rowcount == 1,
        "db_path": str(db_path),
        "task_id": args.task_id,
        "agent_id": args.agent_id,
        "lease_until": lease_until if cursor.rowcount == 1 else None,
    }


def release_expired_claims(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    released: list[dict[str, object]] = []
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        rows = con.execute(
            f"""
            select task_id, assignee_id, lease_until
            from {TASK_TABLE}
            where status in ('claimed', 'running')
              and lease_until is not null
            order by lease_until asc
            limit ?
            """,
            (args.limit,),
        ).fetchall()

        for row in rows:
            lease_until = parse_iso(row["lease_until"])
            if lease_until is None or lease_until > now:
                continue
            update_time = now_iso()
            con.execute(
                f"""
                update {TASK_TABLE}
                set status = 'open',
                    assignee_id = null,
                    claimed_at = null,
                    lease_until = null,
                    heartbeat_at = null,
                    updated_at = ?
                where task_id = ?
                  and status in ('claimed', 'running')
                """,
                (update_time, row["task_id"]),
            )
            released.append(
                {
                    "task_id": row["task_id"],
                    "previous_assignee_id": row["assignee_id"],
                    "expired_at": row["lease_until"],
                }
            )
        con.commit()
    return {
        "db_path": str(db_path),
        "released_count": len(released),
        "released": released,
    }


def unlock_ready_tasks(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    unlocked: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    tasks_to_save: list[GuildTask] = []
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        rows = con.execute(
            f"""
            select payload_json from {TASK_TABLE}
            where status = 'blocked'
            order by coalesce(quest_chain_id, ''), sequence_no, updated_at
            limit ?
            """,
            (args.limit,),
        ).fetchall()

        for row in rows:
            task = GuildTask(**json.loads(row["payload_json"]))
            deps = dependency_statuses(con, task)
            reason = task_unlock_reason(task, deps)
            if reason is not None:
                blocked.append(
                    {
                        "task_id": task.task_id,
                        "title": task.title,
                        "reason": reason,
                        "depends_on": deps,
                    }
                )
                continue

            task.status = "open"
            tasks_to_save.append(task)
            unlocked.append(
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "quest_chain_id": task.quest_chain_id,
                    "sequence_no": task.sequence_no,
                }
            )

    for task in tasks_to_save:
        save_task_record(db_path, task)

    return {
        "db_path": str(db_path),
        "unlocked_count": len(unlocked),
        "blocked_count": len(blocked),
        "unlocked": unlocked,
        "blocked": blocked,
    }


def retry_blocked_task(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    allowed_reasons = set(args.allowed_reason or RETRYABLE_BLOCKED_REASONS)
    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        con.execute("begin immediate")
        row = con.execute(
            f"select payload_json from {TASK_TABLE} where task_id = ?",
            (args.task_id,),
        ).fetchone()
        if row is None:
            con.rollback()
            return {"reopened": False, "reason": "task_not_found", "task_id": args.task_id}

        task = GuildTask(**json.loads(row["payload_json"]))
        if task.status != "blocked":
            con.rollback()
            return {
                "reopened": False,
                "reason": "not_blocked",
                "task_id": task.task_id,
                "status": task.status,
            }

        blocked_reason = task.blocked_reason or "blocked_unknown"
        if blocked_reason not in allowed_reasons:
            con.rollback()
            return {
                "reopened": False,
                "reason": "blocked_reason_not_retryable",
                "task_id": task.task_id,
                "blocked_reason": blocked_reason,
                "allowed_reasons": sorted(allowed_reasons),
            }

        deps = dependency_statuses(con, task)
        readiness_reason = task_unlock_reason(
            task.model_copy(update={"blocked_reason": None}), deps
        )
        if readiness_reason is not None:
            con.rollback()
            return {
                "reopened": False,
                "reason": "not_ready",
                "task_id": task.task_id,
                "blocked_reason": blocked_reason,
                "readiness_reason": readiness_reason,
                "depends_on": deps,
            }

        now = now_iso()
        task.status = "open"
        task.blocked_reason = None
        payload = json.dumps(task.model_dump(mode="json"), sort_keys=True)
        cursor = con.execute(
            f"""
            update {TASK_TABLE}
            set status = 'open',
                assignee_id = null,
                claimed_at = null,
                lease_until = null,
                heartbeat_at = null,
                updated_at = ?,
                payload_json = ?
            where task_id = ?
              and status = 'blocked'
            """,
            (now, payload, task.task_id),
        )
        if cursor.rowcount != 1:
            con.rollback()
            return {
                "reopened": False,
                "reason": "lost_retry_race",
                "task_id": task.task_id,
            }
        con.commit()

    return {
        "reopened": True,
        "db_path": str(db_path),
        "task_id": task.task_id,
        "status": "open",
        "previous_blocked_reason": blocked_reason,
    }


def fake_worker_claim_next(
    con: sqlite3.Connection,
    args: argparse.Namespace,
) -> GuildTask | None:
    agent_skills = split_csv(args.skills)
    if not agent_skills:
        agent_skills = ["general"]
    where = ["status = 'open'"]
    params: list[object] = []
    if args.quest_chain_id:
        where.append("quest_chain_id = ?")
        params.append(args.quest_chain_id)
    where_sql = " and ".join(where)
    now = now_iso()
    now_dt = datetime.now(timezone.utc)
    lease_until = iso_after(args.lease_seconds)
    min_open_age_seconds = max(0, int(args.min_open_age_seconds or 0))

    con.execute("begin immediate")
    rows = con.execute(
        f"""
        select task_id, required_rank, required_skill, updated_at, payload_json
        from {TASK_TABLE}
        where {where_sql}
        order by
            case required_rank
                when 'S' then 5
                when 'A' then 4
                when 'B' then 3
                when 'C' then 2
                when 'D' then 1
                else 0
            end desc,
            coalesce(quest_chain_id, ''),
            sequence_no,
            updated_at asc
        limit ?
        """,
        (*params, args.scan_limit),
    ).fetchall()

    for row in rows:
        task = GuildTask(**json.loads(row["payload_json"]))
        if min_open_age_seconds > 0:
            opened_at = parse_iso(row["updated_at"])
            if opened_at is not None:
                open_age = (now_dt - opened_at).total_seconds()
                if open_age < min_open_age_seconds:
                    continue
        if not rank_can_claim(args.agent_rank, task.required_rank):
            continue
        if not skill_can_claim(agent_skills, task.required_skill):
            continue
        cursor = con.execute(
            f"""
            update {TASK_TABLE}
            set status = 'claimed',
                assignee_id = ?,
                claimed_at = ?,
                lease_until = ?,
                heartbeat_at = ?,
                claim_attempt = claim_attempt + 1,
                updated_at = ?
            where task_id = ? and status = 'open'
            """,
            (
                args.agent_id,
                now,
                lease_until,
                now,
                now,
                task.task_id,
            ),
        )
        if cursor.rowcount == 1:
            con.commit()
            task.status = "claimed"
            return task

    con.rollback()
    return None


def publish_fake_worker_artifact(
    con: sqlite3.Connection,
    task: GuildTask,
    args: argparse.Namespace,
) -> str:
    artifact_id = f"{task.task_id}-{task.output_artifact}-{uuid.uuid4().hex[:8]}"
    payload = {
        "ok": True,
        "mode": "deterministic_fake_worker",
        "task_id": task.task_id,
        "task_type": task.task_type,
        "quest_chain_id": task.quest_chain_id,
        "output_artifact": task.output_artifact,
        "worker": args.agent_id,
        "changed_paths": task.allowed_files,
        "commands_run": [task.test_command] if task.test_command else [],
        "test_result": "passed" if task.task_type in {"execution", "fix"} else "not_required",
        "known_risks": [
            "Fake worker publishes deterministic artifacts only; it does not edit production files.",
        ],
    }
    con.execute(
        f"""
        insert into {ARTIFACT_TABLE} (
            artifact_id, task_id, quest_chain_id, artifact_type,
            producer_agent_id, summary, payload_json, created_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(artifact_id) do update set
            task_id = excluded.task_id,
            quest_chain_id = excluded.quest_chain_id,
            artifact_type = excluded.artifact_type,
            producer_agent_id = excluded.producer_agent_id,
            summary = excluded.summary,
            payload_json = excluded.payload_json,
            created_at = excluded.created_at
        """,
        (
            artifact_id,
            task.task_id,
            task.quest_chain_id,
            task.output_artifact,
            args.agent_id,
            f"Fake worker completed {task.title}",
            json.dumps(payload, sort_keys=True),
            now_iso(),
        ),
    )
    return artifact_id


def complete_fake_worker_task(
    db_path: Path,
    task: GuildTask,
    args: argparse.Namespace,
) -> dict[str, object]:
    if task.task_type == "join_review":
        review_args = argparse.Namespace(
            task_id=task.task_id,
            reviewer_id=args.agent_id,
        )
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "action": "join_review",
            "review": run_join_review(db_path, review_args),
        }

    with connect_task_db(db_path) as con:
        ensure_task_schema(con)
        artifact_id = publish_fake_worker_artifact(con, task, args)
        task.status = "done"
        save_task_record_in_connection(con, task)
        con.commit()
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "action": "complete",
        "artifact_id": artifact_id,
    }


def run_fake_worker(db_path: Path, args: argparse.Namespace) -> dict[str, object]:
    events: list[dict[str, object]] = []
    completed = 0
    unlocked_total = 0

    for _ in range(args.max_steps):
        unlock_args = argparse.Namespace(limit=args.unlock_limit)
        unlock = unlock_ready_tasks(db_path, unlock_args)
        unlocked_total += int(unlock["unlocked_count"])
        if unlock["unlocked_count"]:
            events.append({"action": "unlock_ready", "result": unlock})

        with connect_task_db(db_path) as con:
            ensure_task_schema(con)
            task = fake_worker_claim_next(con, args)

        if task is None:
            events.append({"action": "idle", "reason": "no_claimable_task"})
            break

        events.append(
            {
                "action": "claim",
                "task_id": task.task_id,
                "task_type": task.task_type,
                "title": task.title,
            }
        )
        result = complete_fake_worker_task(db_path, task, args)
        events.append(result)
        completed += 1

        unlock = unlock_ready_tasks(db_path, unlock_args)
        unlocked_total += int(unlock["unlocked_count"])
        if unlock["unlocked_count"]:
            events.append({"action": "unlock_ready", "result": unlock})

        if args.once:
            break

    return {
        "db_path": str(db_path),
        "agent_id": args.agent_id,
        "agent_rank": args.agent_rank,
        "skills": split_csv(args.skills) or ["general"],
        "quest_chain_id": args.quest_chain_id,
        "completed_count": completed,
        "unlocked_count": unlocked_total,
        "events": events,
    }


class ImplementationEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        task = inputs.first_as(GuildTask)
        if task is None:
            return EvalResult.empty()

        result = ImplementationResult(
            task_id=task.task_id,
            quest_chain_id=task.quest_chain_id,
            task_type=task.task_type,
            output_artifact=task.output_artifact,
            worker=agent.name,
            summary=f"Produced {task.output_artifact} for: {task.title}",
            changed_paths=task.allowed_files or ["_runtime/flock/worker_team_prototype.py"],
            commands_run=[task.test_command] if task.test_command else [],
            test_result="pending_test_worker",
            known_risks=[
                "This deterministic prototype does not edit production files.",
            ],
            notes=[
                "No production Hermes blackboard writes.",
                "No model provider calls.",
                "Durable worker state stays in Hermes AppData.",
                f"Plan review status: {task.plan_review_status}.",
            ],
        )
        return EvalResult.from_object(result, agent=agent)


class TestEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        task = inputs.first_as(GuildTask)
        if task is None:
            return EvalResult.empty()

        checks = [
            "artifact schemas are typed with Pydantic",
            "all worker outputs carry task_id",
            "integrator is gated by JoinSpec over task_id",
            "task declares type, rank, skill, and output artifact",
            "task declares owner area and file scope",
            "task declares evidence requirements",
        ]
        if task.test_command:
            checks.append(f"declared test command: {task.test_command}")
        missing = [
            criterion
            for criterion in task.acceptance_criteria
            if "production" in criterion.lower() and "no production" not in task.request.lower()
        ]
        result = TestResult(
            task_id=task.task_id,
            quest_chain_id=task.quest_chain_id,
            task_type=task.task_type,
            output_artifact="test_report",
            worker=agent.name,
            passed=not missing,
            checks=checks,
            failures=missing,
        )
        return EvalResult.from_object(result, agent=agent)


class ReviewEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        task = inputs.first_as(GuildTask)
        if task is None:
            return EvalResult.empty()

        result = ReviewResult(
            task_id=task.task_id,
            quest_chain_id=task.quest_chain_id,
            task_type=task.task_type,
            output_artifact="review_report",
            worker=agent.name,
            approved=task.plan_review_status in {"approved", "not_required"},
            findings=[],
            residual_risks=[
                "Flock dependency sync and provider configuration are not validated here.",
                "Dashboard and production blackboard bridges are intentionally out of scope.",
            ],
            evidence_complete=all(
                item
                in {
                    "artifact",
                    "summary",
                    "files_changed",
                    "commands_run",
                    "test_result",
                    "known_risks",
                }
                for item in task.evidence_required
            ),
            plan_gate_checked=True,
        )
        return EvalResult.from_object(result, agent=agent)


class IntegratorEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        implementations = [
            ImplementationResult(**artifact.payload)
            for artifact in inputs.artifacts
            if artifact.type.endswith("ImplementationResult")
        ]
        tests = [
            TestResult(**artifact.payload)
            for artifact in inputs.artifacts
            if artifact.type.endswith("TestResult")
        ]
        reviews = [
            ReviewResult(**artifact.payload)
            for artifact in inputs.artifacts
            if artifact.type.endswith("ReviewResult")
        ]

        if not implementations or not tests or not reviews:
            return EvalResult.empty()

        implementation = implementations[0]
        test = tests[0]
        review = reviews[0]
        accepted = test.passed and review.approved and review.evidence_complete
        within_fix_budget = len(test.failures) <= 1
        generated_tasks: list[GuildTask] = []
        stop_condition = "none"
        if not accepted and within_fix_budget:
            generated_tasks.append(
                GuildTask(
                    task_id=f"{implementation.task_id}-fix-1",
                    task_type="fix",
                    required_rank="B",
                    required_skill="implementation",
                    owner_area="worker_runtime",
                    status="blocked",
                    plan_review_required=True,
                    plan_review_status="pending",
                    human_approval_required=True,
                    quest_chain_id=implementation.quest_chain_id,
                    sequence_no=99,
                    depends_on=[implementation.task_id],
                    output_artifact="fix_result",
                    generated_from=implementation.task_id,
                    source_artifact="integration_report",
                    max_generated_tasks=0,
                    fix_round=1,
                    title="Fix mismatch found by join review",
                    request="Address failed checks from the integration report.",
                    acceptance_criteria=["failed checks are resolved"],
                    definition_of_done=["review artifact confirms the mismatch is resolved"],
                )
            )
        elif not accepted:
            stop_condition = "escalate_to_hermes"

        result = TaskDecision(
            task_id=implementation.task_id,
            quest_chain_id=implementation.quest_chain_id,
            task_type="join_review",
            output_artifact="integration_report",
            decision="accept" if accepted else "revise",
            summary=(
                "Join review read upstream artifacts and produced an integration decision."
            ),
            required_next_actions=[] if accepted else ["address failed checks"],
            evidence={
                "implementation_summary": implementation.summary,
                "implementation_changed_paths": implementation.changed_paths,
                "implementation_commands_run": implementation.commands_run,
                "implementation_known_risks": implementation.known_risks,
                "test_passed": test.passed,
                "test_failures": test.failures,
                "review_approved": review.approved,
                "evidence_complete": review.evidence_complete,
                "plan_gate_checked": review.plan_gate_checked,
                "review_findings": review.findings,
                "review_residual_risks": review.residual_risks,
            },
            generated_tasks=generated_tasks,
            stop_condition=stop_condition,
        )
        return EvalResult.from_object(result, agent=agent)


def build_flock(store) -> Flock:
    flock = Flock(store=store, no_output=True)

    (
        flock.agent("implementation_worker")
        .description("Creates a deterministic implementation artifact.")
        .consumes(GuildTask)
        .publishes(ImplementationResult)
        .with_engines(ImplementationEngine())
    )
    (
        flock.agent("test_worker")
        .description("Creates a deterministic test artifact.")
        .consumes(GuildTask)
        .publishes(TestResult)
        .with_engines(TestEngine())
    )
    (
        flock.agent("review_worker")
        .description("Creates a deterministic review artifact.")
        .consumes(GuildTask)
        .publishes(ReviewResult)
        .with_engines(ReviewEngine())
    )
    (
        flock.agent("integrator")
        .description("Waits for all worker artifacts and publishes TaskDecision.")
        .consumes(
            ImplementationResult,
            TestResult,
            ReviewResult,
            join=JoinSpec(
                by=lambda artifact: artifact.task_id,
                within=timedelta(minutes=5),
            ),
        )
        .publishes(TaskDecision)
        .with_engines(IntegratorEngine())
    )

    return flock


async def run(db_path: Path, store_kind: str) -> dict[str, object]:
    if store_kind == "sqlite":
        db_path.parent.mkdir(parents=True, exist_ok=True)
        store = SQLiteBlackboardStore(db_path)
    elif store_kind == "memory":
        store = InMemoryBlackboardStore()
    else:
        raise ValueError(f"Unsupported store kind: {store_kind}")

    flock = build_flock(store)

    task_id = f"guild-task-{uuid.uuid4().hex[:8]}"
    quest_chain_id = f"quest-chain-{uuid.uuid4().hex[:8]}"
    task = GuildTask(
        task_id=task_id,
        task_type="execution",
        required_rank="B",
        required_skill="worker_runtime",
        owner_area="worker_team_runtime",
        status="open",
        plan_review_required=True,
        plan_review_status="approved",
        quest_chain_id=quest_chain_id,
        sequence_no=2,
        depends_on=["contract-task"],
        linked_tasks=["contract-task", "join-review-task"],
        output_artifact="worker_runtime_result",
        allowed_files=["_runtime/flock/worker_team_prototype.py"],
        forbidden_files=["C:/Users/nthan/AppData/Local/hermes/.env", "auth.json"],
        title="Validate isolated Flock Worker Team prototype",
        request=(
            "Use deterministic workers only; no production Hermes blackboard; "
            "no model provider calls."
        ),
        acceptance_criteria=[
            "implementation result is published",
            "test result is published",
            "review result is published",
            "integrator waits for all required artifacts",
            "no production integration",
        ],
        definition_of_done=[
            "all deterministic worker artifacts are present",
            "join review emits accept or bounded revise decision",
        ],
        test_command=(
            "_runtime\\research\\flock\\.venv\\Scripts\\python.exe "
            "_runtime\\flock\\worker_team_prototype.py --store sqlite"
        ),
        style_guide="HermesGuildCore markdown-first, small reversible runtime changes.",
    )
    if store_kind == "sqlite":
        save_task_record(db_path, task)

    try:
        if hasattr(store, "ensure_schema"):
            await store.ensure_schema()
        await flock.publish(task, correlation_id=task_id)
        await flock.run_until_idle(timeout=30)

        implementation_results = await flock.store.get_by_type(
            ImplementationResult, correlation_id=task_id
        )
        test_results = await flock.store.get_by_type(TestResult, correlation_id=task_id)
        review_results = await flock.store.get_by_type(
            ReviewResult, correlation_id=task_id
        )
        decisions = await flock.store.get_by_type(TaskDecision, correlation_id=task_id)

        return {
            "task_id": task_id,
            "store": store_kind,
            "db_path": str(db_path) if store_kind == "sqlite" else None,
            "implementation_results": len(implementation_results),
            "test_results": len(test_results),
            "review_results": len(review_results),
            "task_decisions": len(decisions),
            "decision": decisions[0].model_dump() if decisions else None,
        }
    finally:
        if hasattr(store, "close"):
            await store.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the isolated HermesGuildCore Flock Worker Team prototype."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite path for durable Flock artifacts.",
    )
    parser.add_argument(
        "--store",
        choices=["sqlite", "memory"],
        default="sqlite",
        help="Use sqlite for the target gate or memory for orchestration smoke tests.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser(
        "run-demo",
        help="Run the deterministic GuildTask -> artifacts -> TaskDecision demo.",
    )

    create = sub.add_parser("create-task", help="Create or upsert a durable GuildTask.")
    create.add_argument("--task-id")
    create.add_argument(
        "--task-type",
        choices=["contract", "execution", "join_review", "fix", "final_review"],
        default="execution",
    )
    create.add_argument("--required-rank", choices=["S", "A", "B", "C", "D"], default="C")
    create.add_argument("--required-skill", default="general")
    create.add_argument("--owner-area", default="general")
    create.add_argument(
        "--status",
        choices=["blocked", "open", "claimed", "running", "review", "done", "failed", "cancelled"],
        default="blocked",
    )
    create.add_argument("--plan-review-not-required", action="store_true")
    create.add_argument(
        "--plan-review-status",
        choices=["not_required", "pending", "approved", "rejected"],
        default="pending",
    )
    create.add_argument("--human-approval-required", action="store_true")
    create.add_argument("--quest-chain-id")
    create.add_argument("--sequence-no", type=int, default=0)
    create.add_argument("--depends-on", help="Comma-separated task ids.")
    create.add_argument("--linked-tasks", help="Comma-separated task ids.")
    create.add_argument("--input-artifacts", help="Comma-separated artifact ids or names.")
    create.add_argument("--output-artifact", default="worker_result")
    create.add_argument("--allowed-files", help="Comma-separated path globs.")
    create.add_argument("--forbidden-files", help="Comma-separated path globs.")
    create.add_argument("--generated-from")
    create.add_argument("--source-artifact")
    create.add_argument("--max-generated-tasks", type=int, default=0)
    create.add_argument("--max-fix-rounds", type=int, default=3)
    create.add_argument("--fix-round", type=int, default=0)
    create.add_argument("--max-spawned-tasks-per-join", type=int, default=5)
    create.add_argument("--max-spawned-tasks-per-chain", type=int, default=20)
    create.add_argument("--human-approval-after-failed-rounds", type=int, default=2)
    create.add_argument("--budget-token-limit", type=int)
    create.add_argument("--title", required=True)
    create.add_argument("--request")
    create.add_argument("--request-file")
    create.add_argument("--acceptance-criteria", action="append")
    create.add_argument("--definition-of-done", action="append")
    create.add_argument("--test-command")
    create.add_argument("--style-guide")

    list_cmd = sub.add_parser("list-tasks", help="List durable GuildTask records.")
    list_cmd.add_argument("--status")
    list_cmd.add_argument("--quest-chain-id")
    list_cmd.add_argument("--limit", type=int, default=20)

    inspect = sub.add_parser("inspect-task", help="Inspect one durable GuildTask record.")
    inspect.add_argument("task_id")

    status = sub.add_parser("set-status", help="Set a task status for scheduler tests.")
    status.add_argument("task_id")
    status.add_argument(
        "status",
        choices=["blocked", "open", "claimed", "running", "review", "done", "failed", "cancelled"],
    )
    status.add_argument("--blocked-reason")

    unlock = sub.add_parser(
        "unlock-ready",
        help="Open blocked tasks whose plan gate and dependencies are satisfied.",
    )
    unlock.add_argument("--limit", type=int, default=50)

    retry = sub.add_parser(
        "retry-blocked",
        help="Reopen one blocked task only when its blocked_reason is retryable.",
    )
    retry.add_argument("task_id")
    retry.add_argument(
        "--allowed-reason",
        action="append",
        choices=sorted(RETRYABLE_BLOCKED_REASONS),
        help="Override the retryable blocked reasons. Repeat to allow multiple reasons.",
    )

    claim = sub.add_parser(
        "claim-next",
        help="Atomically claim the next open task matching agent rank and skills.",
    )
    claim.add_argument("--agent-id", required=True)
    claim.add_argument("--agent-rank", choices=["S", "A", "B", "C", "D"], required=True)
    claim.add_argument("--skills", default="general", help="Comma-separated skills.")
    claim.add_argument("--task-id")
    claim.add_argument("--quest-chain-id")
    claim.add_argument("--lease-seconds", type=int, default=900)
    claim.add_argument("--scan-limit", type=int, default=50)
    claim.add_argument("--min-open-age-seconds", type=int, default=0)

    heartbeat = sub.add_parser("heartbeat", help="Extend a claimed/running task lease.")
    heartbeat.add_argument("--agent-id", required=True)
    heartbeat.add_argument("--task-id", required=True)
    heartbeat.add_argument("--lease-seconds", type=int, default=900)

    release = sub.add_parser(
        "release-expired",
        help="Release claimed/running tasks whose lease has expired.",
    )
    release.add_argument("--limit", type=int, default=50)

    artifact = sub.add_parser("publish-artifact", help="Publish a durable task artifact.")
    artifact.add_argument("--artifact-id")
    artifact.add_argument("--task-id", required=True)
    artifact.add_argument("--artifact-type", default="worker_result")
    artifact.add_argument("--producer-agent-id", required=True)
    artifact.add_argument("--summary", required=True)
    artifact.add_argument(
        "--payload-json",
        default="{}",
        help="JSON object payload. Example: '{\"ok\": true}'.",
    )
    artifact.add_argument(
        "--payload-json-file",
        help="Read artifact payload JSON object from a file instead of argv.",
    )

    artifacts = sub.add_parser("list-artifacts", help="List durable task artifacts.")
    artifacts.add_argument("--task-id")
    artifacts.add_argument("--quest-chain-id")
    artifacts.add_argument("--limit", type=int, default=20)

    join_review = sub.add_parser(
        "run-join-review",
        help="Run a queued join_review task over published artifacts.",
    )
    join_review.add_argument("--task-id", required=True)
    join_review.add_argument("--reviewer-id", default="hermes-reviewer")

    fake_worker = sub.add_parser(
        "run-fake-worker",
        help="Run a deterministic worker loop over claimable tasks.",
    )
    fake_worker.add_argument("--agent-id", default="fake-worker")
    fake_worker.add_argument("--agent-rank", choices=["S", "A", "B", "C", "D"], default="S")
    fake_worker.add_argument("--skills", default="general", help="Comma-separated skills.")
    fake_worker.add_argument("--quest-chain-id")
    fake_worker.add_argument("--max-steps", type=int, default=10)
    fake_worker.add_argument("--scan-limit", type=int, default=50)
    fake_worker.add_argument("--lease-seconds", type=int, default=900)
    fake_worker.add_argument("--min-open-age-seconds", type=int, default=0)
    fake_worker.add_argument("--unlock-limit", type=int, default=50)
    fake_worker.add_argument("--once", action="store_true")

    seed_demo = sub.add_parser(
        "seed-demo-chain",
        help="Seed or reset the demo-even-random-app quest chain.",
    )
    seed_demo.add_argument("--quest-chain-id", default="demo-even-random-app")
    seed_demo.add_argument("--reset", action="store_true")

    dashboard = sub.add_parser(
        "dashboard",
        help="Return a stable read model for terminal/UI dashboard use.",
    )
    dashboard.add_argument("--quest-chain-id")
    dashboard.add_argument("--limit", type=int, default=100)
    dashboard.add_argument("--artifact-limit", type=int, default=50)
    dashboard.add_argument("--include-tasks", action="store_true")
    dashboard.add_argument("--include-artifacts", action="store_true")
    dashboard.add_argument("--format", choices=["json", "text"], default="json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = args.db.resolve()
    if args.cmd == "create-task":
        summary = create_task(db_path, args)
    elif args.cmd == "list-tasks":
        summary = list_tasks(db_path, args)
    elif args.cmd == "inspect-task":
        summary = inspect_task(db_path, args)
    elif args.cmd == "set-status":
        summary = update_task_status(db_path, args)
    elif args.cmd == "unlock-ready":
        summary = unlock_ready_tasks(db_path, args)
    elif args.cmd == "retry-blocked":
        summary = retry_blocked_task(db_path, args)
    elif args.cmd == "claim-next":
        summary = claim_next_task(db_path, args)
    elif args.cmd == "heartbeat":
        summary = heartbeat_task(db_path, args)
    elif args.cmd == "release-expired":
        summary = release_expired_claims(db_path, args)
    elif args.cmd == "publish-artifact":
        summary = publish_artifact(db_path, args)
    elif args.cmd == "list-artifacts":
        summary = list_artifacts(db_path, args)
    elif args.cmd == "run-join-review":
        summary = run_join_review(db_path, args)
    elif args.cmd == "run-fake-worker":
        summary = run_fake_worker(db_path, args)
    elif args.cmd == "seed-demo-chain":
        summary = seed_demo_chain(db_path, args)
    elif args.cmd == "dashboard":
        summary = dashboard_snapshot(db_path, args)
    else:
        summary = asyncio.run(run(db_path, args.store))
    if args.cmd == "dashboard" and args.format == "text":
        print(format_dashboard_text(summary))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
