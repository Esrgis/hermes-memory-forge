import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = (
    Path(os.environ["LOCALAPPDATA"]) / "hermes" / "blackboard" / "blackboard.sqlite"
    if os.environ.get("LOCALAPPDATA")
    else Path.home() / ".hermes" / "blackboard" / "blackboard.sqlite"
)
DB_PATH = Path(
    os.environ.get(
        "HERMES_BLACKBOARD_DB",
        str(DEFAULT_DB_PATH),
    )
)
try:
    TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("pragma busy_timeout=30000")
    con.execute("pragma journal_mode=wal")
    con.execute("pragma synchronous=normal")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        create table if not exists tasks (
            id integer primary key autoincrement,
            title text not null,
            status text not null default 'open',
            source text not null default 'manual',
            priority integer not null default 3,
            due_at text,
            created_at text not null,
            updated_at text not null,
            notes text not null default ''
        );

        create table if not exists events (
            id integer primary key autoincrement,
            kind text not null,
            summary text not null,
            payload_json text not null default '{}',
            created_at text not null
        );

        create table if not exists decisions (
            id integer primary key autoincrement,
            title text not null,
            summary text not null,
            created_at text not null
        );

        create table if not exists memory_candidates (
            id integer primary key autoincrement,
            content text not null,
            status text not null default 'candidate',
            source text not null default 'manual',
            created_at text not null,
            reviewed_at text
        );

        create table if not exists workflow_runs (
            id integer primary key autoincrement,
            name text not null,
            status text not null,
            started_at text not null,
            finished_at text,
            summary text not null default ''
        );

        create table if not exists checkins (
            id integer primary key autoincrement,
            date text not null,
            name text not null,
            status text not null default 'pending',
            created_at text not null,
            updated_at text not null,
            unique(date, name)
        );

        create table if not exists current_state (
            key text primary key,
            value_json text not null,
            updated_at text not null,
            stale_after text,
            source text not null default 'manual'
        );

        create table if not exists agent_status (
            name text primary key,
            status text not null,
            role text not null default '',
            updated_at text not null,
            summary text not null default ''
        );
        """
    )
    con.commit()


def add_event(con: sqlite3.Connection, kind: str, summary: str, payload: dict | None = None) -> None:
    con.execute(
        "insert into events(kind, summary, payload_json, created_at) values (?, ?, ?, ?)",
        (kind, summary, json.dumps(payload or {}, ensure_ascii=False), now_iso()),
    )
    con.commit()


def command_init(args: argparse.Namespace) -> None:
    with connect() as con:
        init_db(con)
        add_event(con, "blackboard.init", "Blackboard initialized")
    print(str(DB_PATH))


def command_event(args: argparse.Namespace) -> None:
    with connect() as con:
        init_db(con)
        add_event(con, args.kind, args.summary)
    print("ok")


def command_task(args: argparse.Namespace) -> None:
    ts = now_iso()
    with connect() as con:
        init_db(con)
        con.execute(
            """
            insert into tasks(title, status, source, priority, due_at, created_at, updated_at, notes)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (args.title, args.status, args.source, args.priority, args.due_at, ts, ts, args.notes),
        )
        con.commit()
    print("ok")


def command_checkin_create(args: argparse.Namespace) -> None:
    date = args.date or datetime.now(TZ).date().isoformat()
    ts = now_iso()
    with connect() as con:
        init_db(con)
        con.execute(
            """
            insert into checkins(date, name, status, created_at, updated_at)
            values (?, ?, 'pending', ?, ?)
            on conflict(date, name) do update set status='pending', updated_at=excluded.updated_at
            """,
            (date, args.name, ts, ts),
        )
        add_event(con, "checkin.pending", f"Check-in pending: {args.name}", {"date": date})
    print("ok")


def command_checkin_mark(args: argparse.Namespace) -> None:
    date = args.date or datetime.now(TZ).date().isoformat()
    ts = now_iso()
    with connect() as con:
        init_db(con)
        con.execute(
            """
            insert into checkins(date, name, status, created_at, updated_at)
            values (?, ?, ?, ?, ?)
            on conflict(date, name) do update set status=excluded.status, updated_at=excluded.updated_at
            """,
            (date, args.name, args.status, ts, ts),
        )
        add_event(con, "checkin.mark", f"Check-in {args.name}: {args.status}", {"date": date})
    print("ok")


def command_checkin_status(args: argparse.Namespace) -> None:
    date = args.date or datetime.now(TZ).date().isoformat()
    with connect() as con:
        init_db(con)
        row = con.execute(
            "select status from checkins where date=? and name=?",
            (date, args.name),
        ).fetchone()
    print(row["status"] if row else "missing")


def command_summary(args: argparse.Namespace) -> None:
    with connect() as con:
        init_db(con)
        counts = {
            "tasks_open": con.execute("select count(*) c from tasks where status='open'").fetchone()["c"],
            "events": con.execute("select count(*) c from events").fetchone()["c"],
            "memory_candidates": con.execute("select count(*) c from memory_candidates").fetchone()["c"],
            "workflow_runs": con.execute("select count(*) c from workflow_runs").fetchone()["c"],
            "current_state": con.execute("select count(*) c from current_state").fetchone()["c"],
            "agent_status": con.execute("select count(*) c from agent_status").fetchone()["c"],
        }
    print(json.dumps(counts, ensure_ascii=False))


def command_task_list(args: argparse.Namespace) -> None:
    with connect() as con:
        init_db(con)
        rows = con.execute(
            """
            select id, title, status, source, priority, due_at, updated_at, notes
            from tasks
            where (? is null or status = ?)
            order by priority asc, updated_at desc
            limit ?
            """,
            (args.status, args.status, args.limit),
        ).fetchall()
    print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))


def command_event_list(args: argparse.Namespace) -> None:
    with connect() as con:
        init_db(con)
        rows = con.execute(
            """
            select id, kind, summary, payload_json, created_at
            from events
            order by id desc
            limit ?
            """,
            (args.limit,),
        ).fetchall()
    print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))


def command_state_set(args: argparse.Namespace) -> None:
    ts = now_iso()
    try:
        parsed = json.loads(args.value_json)
        value_json = json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"value_json must be valid JSON: {exc}") from exc

    with connect() as con:
        init_db(con)
        con.execute(
            """
            insert into current_state(key, value_json, updated_at, stale_after, source)
            values (?, ?, ?, ?, ?)
            on conflict(key) do update set
                value_json=excluded.value_json,
                updated_at=excluded.updated_at,
                stale_after=excluded.stale_after,
                source=excluded.source
            """,
            (args.key, value_json, ts, args.stale_after, args.source),
        )
        add_event(con, "current_state.set", f"Current state updated: {args.key}", {"source": args.source})
    print("ok")


def command_state_get(args: argparse.Namespace) -> None:
    with connect() as con:
        init_db(con)
        row = con.execute(
            "select key, value_json, updated_at, stale_after, source from current_state where key=?",
            (args.key,),
        ).fetchone()
    if not row:
        print("missing")
        return

    item = dict(row)
    item["value"] = json.loads(item.pop("value_json"))
    print(json.dumps(item, ensure_ascii=False, indent=2))


def command_state_list(args: argparse.Namespace) -> None:
    with connect() as con:
        init_db(con)
        rows = con.execute(
            """
            select key, value_json, updated_at, stale_after, source
            from current_state
            order by updated_at desc
            limit ?
            """,
            (args.limit,),
        ).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item["value"] = json.loads(item.pop("value_json"))
        items.append(item)
    print(json.dumps(items, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.set_defaults(func=command_init)

    p = sub.add_parser("event")
    p.add_argument("kind")
    p.add_argument("summary")
    p.set_defaults(func=command_event)

    p = sub.add_parser("task")
    p.add_argument("title")
    p.add_argument("--status", default="open")
    p.add_argument("--source", default="manual")
    p.add_argument("--priority", type=int, default=3)
    p.add_argument("--due-at", default=None)
    p.add_argument("--notes", default="")
    p.set_defaults(func=command_task)

    p = sub.add_parser("task-list")
    p.add_argument("--status", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=command_task_list)

    p = sub.add_parser("event-list")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=command_event_list)

    p = sub.add_parser("checkin-create")
    p.add_argument("name")
    p.add_argument("--date", default=None)
    p.set_defaults(func=command_checkin_create)

    p = sub.add_parser("checkin-mark")
    p.add_argument("name")
    p.add_argument("--status", default="done")
    p.add_argument("--date", default=None)
    p.set_defaults(func=command_checkin_mark)

    p = sub.add_parser("checkin-status")
    p.add_argument("name")
    p.add_argument("--date", default=None)
    p.set_defaults(func=command_checkin_status)

    p = sub.add_parser("summary")
    p.set_defaults(func=command_summary)

    p = sub.add_parser("state-set")
    p.add_argument("key")
    p.add_argument("value_json")
    p.add_argument("--source", default="manual")
    p.add_argument("--stale-after", default=None)
    p.set_defaults(func=command_state_set)

    p = sub.add_parser("state-get")
    p.add_argument("key")
    p.set_defaults(func=command_state_get)

    p = sub.add_parser("state-list")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=command_state_list)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
