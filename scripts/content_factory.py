from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = ROOT / "_runtime" / "content-factory"
DEFAULT_DB = (
    Path(os.environ["LOCALAPPDATA"]) / "hermes" / "content-factory" / "content_factory.sqlite"
    if os.environ.get("LOCALAPPDATA")
    else Path.home() / ".hermes" / "content-factory" / "content_factory.sqlite"
)
DEFAULT_RUNS = DEFAULT_RUNTIME / "runs"
try:
    TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")

JOB_STATUSES = {
    "idea_pending",
    "script_done",
    "render_done",
    "approval_pending",
    "approved",
    "rejected",
    "failed",
}


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:64] or "content-job"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("pragma busy_timeout=30000")
    con.execute("pragma journal_mode=wal")
    con.execute("pragma synchronous=normal")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        create table if not exists content_jobs (
            id text primary key,
            status text not null,
            topic text not null default '',
            niche text not null default '',
            language text not null default 'vi',
            style text not null default '',
            platform text not null default 'tiktok',
            source text not null default 'manual',
            created_at text not null,
            updated_at text not null,
            approved_at text,
            rejected_at text,
            reject_reason text
        );

        create table if not exists content_artifacts (
            id text primary key,
            job_id text not null,
            kind text not null,
            path text,
            text_content text,
            metadata_json text not null default '{}',
            created_at text not null,
            foreign key(job_id) references content_jobs(id)
        );

        create table if not exists approval_events (
            id integer primary key autoincrement,
            job_id text not null,
            channel text not null,
            message_id text,
            decision text,
            payload_json text not null default '{}',
            created_at text not null,
            foreign key(job_id) references content_jobs(id)
        );

        create index if not exists idx_content_jobs_status
        on content_jobs(status, updated_at);

        create index if not exists idx_content_artifacts_job
        on content_artifacts(job_id, kind, created_at);
        """
    )
    con.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def fetch_job(con: sqlite3.Connection, job_id: str) -> dict:
    row = con.execute("select * from content_jobs where id = ?", (job_id,)).fetchone()
    if row is None:
        raise SystemExit(f"job not found: {job_id}")
    return dict(row)


def set_status(
    con: sqlite3.Connection,
    job_id: str,
    status: str,
    *,
    reject_reason: str | None = None,
) -> None:
    if status not in JOB_STATUSES:
        raise SystemExit(f"invalid status: {status}")
    ts = now_iso()
    if status == "approved":
        con.execute(
            """
            update content_jobs
            set status = ?, approved_at = ?, updated_at = ?
            where id = ?
            """,
            (status, ts, ts, job_id),
        )
    elif status == "rejected":
        con.execute(
            """
            update content_jobs
            set status = ?, rejected_at = ?, reject_reason = ?, updated_at = ?
            where id = ?
            """,
            (status, ts, reject_reason or "", ts, job_id),
        )
    else:
        con.execute(
            "update content_jobs set status = ?, updated_at = ? where id = ?",
            (status, ts, job_id),
        )
    con.commit()


def artifact_path(runs_root: Path, job_id: str, filename: str) -> Path:
    path = runs_root / job_id / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def save_artifact(
    con: sqlite3.Connection,
    *,
    job_id: str,
    kind: str,
    path: Path | None = None,
    text_content: str | None = None,
    metadata: dict | None = None,
) -> dict:
    artifact_id = f"artifact-{uuid.uuid4().hex[:10]}"
    row = {
        "id": artifact_id,
        "job_id": job_id,
        "kind": kind,
        "path": rel(path) if path else None,
        "text_content": text_content,
        "metadata_json": json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
        "created_at": now_iso(),
    }
    con.execute(
        """
        insert into content_artifacts(id, job_id, kind, path, text_content, metadata_json, created_at)
        values (:id, :job_id, :kind, :path, :text_content, :metadata_json, :created_at)
        """,
        row,
    )
    con.commit()
    return row


def latest_artifacts(con: sqlite3.Connection, job_id: str) -> dict[str, dict]:
    rows = con.execute(
        """
        select * from content_artifacts
        where job_id = ?
        order by created_at asc, id asc
        """,
        (job_id,),
    ).fetchall()
    latest: dict[str, dict] = {}
    for row in rows:
        latest[row["kind"]] = dict(row)
    return latest


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def generate_content(job: dict) -> dict[str, str]:
    topic = job["topic"].strip() or "mot y tuong hang ngay"
    niche = job["niche"].strip() or "doi song"
    language = job["language"].strip() or "vi"
    style = job["style"].strip() or "thang than, ngan gon"

    if language.lower().startswith("en"):
        hook = f"Most people miss this about {topic}."
        script = "\n".join(
            [
                hook,
                f"If you care about {niche}, start with one small observation.",
                "The useful move is to make it visible, simple, and repeatable.",
                "Save this and test it today.",
            ]
        )
        caption = f"{topic} in one practical minute. #{slugify(niche)} #shorts #creator"
    else:
        hook = f"Da so nguoi bo qua dieu nay ve {topic}."
        script = "\n".join(
            [
                hook,
                f"Neu ban quan tam den {niche}, hay bat dau tu mot quan sat nho.",
                "Dieu co ich la lam no ro rang, don gian, va lap lai duoc.",
                "Luu lai va thu ngay hom nay.",
            ]
        )
        caption = f"{topic} trong mot phut thuc te. #{slugify(niche)} #tiktok #shorts"

    idea = {
        "topic": topic,
        "niche": niche,
        "language": language,
        "style": style,
        "angle": "practical micro-lesson",
        "source": job["source"],
    }
    return {
        "idea_json": json.dumps(idea, ensure_ascii=False, indent=2),
        "hook": hook,
        "script": script,
        "caption": caption,
    }


def build_approval_message(con: sqlite3.Connection, job_id: str) -> str:
    job = fetch_job(con, job_id)
    artifacts = latest_artifacts(con, job_id)
    script_text = artifacts.get("script", {}).get("text_content") or "(missing script)"
    caption_text = artifacts.get("caption", {}).get("text_content") or "(missing caption)"
    video_path = artifacts.get("video_placeholder", {}).get("path") or "(missing video placeholder)"
    return "\n".join(
        [
            "Content Factory approval",
            f"Job: {job_id}",
            f"Topic: {job['topic']}",
            f"Status: {job['status']}",
            "",
            "SCRIPT:",
            script_text,
            "",
            "CAPTION:",
            caption_text,
            "",
            f"Artifact: {video_path}",
            "",
            f"Approve: python scripts/content_factory.py mark-decision --job-id {job_id} --decision approved",
            f"Reject: python scripts/content_factory.py mark-decision --job-id {job_id} --decision rejected --reason \"...\"",
        ]
    )


def resolve_powershell() -> str:
    for candidate in ("powershell", "pwsh"):
        found = shutil.which(candidate)
        if found:
            return found
    raise SystemExit("PowerShell executable not found. Install pwsh or add powershell to PATH.")


def output(value: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value.get("message") or json.dumps(value, ensure_ascii=False))


def command_init(args: argparse.Namespace) -> None:
    with connect(args.db) as con:
        init_db(con)
    output({"ok": True, "db": str(args.db), "runs": str(args.runs)}, args.json)


def command_create_job(args: argparse.Namespace) -> None:
    job_id = args.job_id or f"job-{datetime.now(TZ).strftime('%Y%m%d-%H%M%S')}-{slugify(args.topic)}"
    ts = now_iso()
    with connect(args.db) as con:
        init_db(con)
        con.execute(
            """
            insert into content_jobs(
                id, status, topic, niche, language, style, platform, source, created_at, updated_at
            )
            values (?, 'idea_pending', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                args.topic,
                args.niche or "",
                args.language,
                args.style or "",
                args.platform,
                args.source,
                ts,
                ts,
            ),
        )
        con.commit()
        job = fetch_job(con, job_id)
    output({"ok": True, "job": job, "message": job_id}, args.json)


def command_generate_script(args: argparse.Namespace) -> None:
    with connect(args.db) as con:
        init_db(con)
        job = fetch_job(con, args.job_id)
        generated = generate_content(job)
        idea_path = artifact_path(args.runs, args.job_id, "idea.json")
        script_path = artifact_path(args.runs, args.job_id, "script.md")
        caption_path = artifact_path(args.runs, args.job_id, "caption.md")
        write_text(idea_path, generated["idea_json"])
        write_text(script_path, generated["script"])
        write_text(caption_path, generated["caption"])
        artifacts = [
            save_artifact(
                con,
                job_id=args.job_id,
                kind="idea",
                path=idea_path,
                text_content=generated["idea_json"],
            ),
            save_artifact(
                con,
                job_id=args.job_id,
                kind="script",
                path=script_path,
                text_content=generated["script"],
                metadata={"hook": generated["hook"]},
            ),
            save_artifact(
                con,
                job_id=args.job_id,
                kind="caption",
                path=caption_path,
                text_content=generated["caption"],
            ),
        ]
        set_status(con, args.job_id, "script_done")
    output({"ok": True, "job_id": args.job_id, "artifacts": artifacts}, args.json)


def command_render_placeholder(args: argparse.Namespace) -> None:
    with connect(args.db) as con:
        init_db(con)
        job = fetch_job(con, args.job_id)
        artifacts = latest_artifacts(con, args.job_id)
        script_text = artifacts.get("script", {}).get("text_content") or ""
        caption_text = artifacts.get("caption", {}).get("text_content") or ""
        placeholder_path = artifact_path(args.runs, args.job_id, "video-placeholder.txt")
        write_text(
            placeholder_path,
            "\n".join(
                [
                    f"Video placeholder for {args.job_id}",
                    f"Platform: {job['platform']}",
                    "",
                    "Script:",
                    script_text,
                    "",
                    "Caption:",
                    caption_text,
                    "",
                    "MVP note: replace this with TTS/render output after approval loop is stable.",
                ]
            ),
        )
        artifact = save_artifact(
            con,
            job_id=args.job_id,
            kind="video_placeholder",
            path=placeholder_path,
            metadata={"format": "text-placeholder"},
        )
        set_status(con, args.job_id, "render_done")
    output({"ok": True, "job_id": args.job_id, "artifact": artifact}, args.json)


def command_approval_message(args: argparse.Namespace) -> None:
    with connect(args.db) as con:
        init_db(con)
        message = build_approval_message(con, args.job_id)
        if args.set_pending:
            set_status(con, args.job_id, "approval_pending")
    if args.json:
        output({"ok": True, "job_id": args.job_id, "text": message}, True)
    else:
        print(message)


def command_send_approval(args: argparse.Namespace) -> None:
    with connect(args.db) as con:
        init_db(con)
        message = build_approval_message(con, args.job_id)

    if args.dry_run:
        result = {"ok": True, "dry_run": True, "text": message}
        output({"ok": True, "job_id": args.job_id, "telegram": result}, args.json)
        return

    with connect(args.db) as con:
        init_db(con)
        set_status(con, args.job_id, "approval_pending")

    script = ROOT / "scripts" / "send-telegram-home.ps1"
    completed = subprocess.run(
        [
            resolve_powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Text",
            message,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=args.timeout,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr or completed.stdout or "telegram send failed")
    try:
        result = json.loads((completed.stdout or "").strip())
    except json.JSONDecodeError:
        result = {"ok": True, "raw": completed.stdout}

    with connect(args.db) as con:
        init_db(con)
        con.execute(
            """
            insert into approval_events(job_id, channel, message_id, decision, payload_json, created_at)
            values (?, 'telegram', ?, null, ?, ?)
            """,
            (
                args.job_id,
                str(result.get("message_id") or ""),
                json.dumps(result, ensure_ascii=False, sort_keys=True),
                now_iso(),
            ),
        )
        con.commit()
    output({"ok": True, "job_id": args.job_id, "telegram": result}, args.json)


def command_mark_decision(args: argparse.Namespace) -> None:
    if args.decision not in {"approved", "rejected"}:
        raise SystemExit("decision must be approved or rejected")
    with connect(args.db) as con:
        init_db(con)
        fetch_job(con, args.job_id)
        set_status(con, args.job_id, args.decision, reject_reason=args.reason)
        payload = {"reason": args.reason or ""}
        con.execute(
            """
            insert into approval_events(job_id, channel, message_id, decision, payload_json, created_at)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                args.job_id,
                args.channel,
                args.message_id or "",
                args.decision,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                now_iso(),
            ),
        )
        con.commit()
        job = fetch_job(con, args.job_id)
    output({"ok": True, "job": job}, args.json)


def command_show_job(args: argparse.Namespace) -> None:
    with connect(args.db) as con:
        init_db(con)
        job = fetch_job(con, args.job_id)
        artifacts = [
            dict(row)
            for row in con.execute(
                "select * from content_artifacts where job_id = ? order by created_at",
                (args.job_id,),
            ).fetchall()
        ]
        approvals = [
            dict(row)
            for row in con.execute(
                "select * from approval_events where job_id = ? order by id",
                (args.job_id,),
            ).fetchall()
        ]
    output({"ok": True, "job": job, "artifacts": artifacts, "approval_events": approvals}, True)


def command_list_jobs(args: argparse.Namespace) -> None:
    with connect(args.db) as con:
        init_db(con)
        rows = con.execute(
            """
            select * from content_jobs
            where (? is null or status = ?)
            order by updated_at desc
            limit ?
            """,
            (args.status, args.status, args.limit),
        ).fetchall()
    output({"ok": True, "jobs": [dict(row) for row in rows]}, True)


def command_next_job(args: argparse.Namespace) -> None:
    with connect(args.db) as con:
        init_db(con)
        row = con.execute(
            """
            select * from content_jobs
            where status = ?
            order by created_at asc
            limit 1
            """,
            (args.status,),
        ).fetchone()
    output({"ok": row is not None, "job": row_to_dict(row)}, True)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local AI content factory MVP queue.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    add_common(p)
    p.set_defaults(func=command_init)

    p = sub.add_parser("create-job")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--niche", default="")
    p.add_argument("--language", default="vi")
    p.add_argument("--style", default="")
    p.add_argument("--platform", default="tiktok")
    p.add_argument("--source", default="manual")
    p.add_argument("--job-id")
    p.set_defaults(func=command_create_job)

    p = sub.add_parser("generate-script")
    add_common(p)
    p.add_argument("--job-id", required=True)
    p.set_defaults(func=command_generate_script)

    p = sub.add_parser("render-placeholder")
    add_common(p)
    p.add_argument("--job-id", required=True)
    p.set_defaults(func=command_render_placeholder)

    p = sub.add_parser("approval-message")
    add_common(p)
    p.add_argument("--job-id", required=True)
    p.add_argument("--set-pending", action="store_true")
    p.set_defaults(func=command_approval_message)

    p = sub.add_parser("send-approval")
    add_common(p)
    p.add_argument("--job-id", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--timeout", type=int, default=30)
    p.set_defaults(func=command_send_approval)

    p = sub.add_parser("mark-decision")
    add_common(p)
    p.add_argument("--job-id", required=True)
    p.add_argument("--decision", required=True, choices=["approved", "rejected"])
    p.add_argument("--reason", default="")
    p.add_argument("--channel", default="manual")
    p.add_argument("--message-id", default="")
    p.set_defaults(func=command_mark_decision)

    p = sub.add_parser("show-job")
    add_common(p)
    p.add_argument("--job-id", required=True)
    p.set_defaults(func=command_show_job)

    p = sub.add_parser("list-jobs")
    add_common(p)
    p.add_argument("--status")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=command_list_jobs)

    p = sub.add_parser("next-job")
    add_common(p)
    p.add_argument("--status", default="idea_pending")
    p.set_defaults(func=command_next_job)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
