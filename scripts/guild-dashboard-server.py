from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
import re
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def safe_session_part(value: Any) -> str:
    text = str(value or "session")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or "session"


def ps_quote(value: Any) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


def enrich_repaired_dashboard(data: dict[str, Any]) -> dict[str, Any]:
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return data

    done_fixes_by_source: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if str(task.get("task_type") or "") != "fix" or str(task.get("status") or "") != "done":
            continue
        source = str(task.get("generated_from") or "")
        if source:
            done_fixes_by_source[source] = task

    repaired_ids: list[str] = []
    unrepaired_failed_ids: list[str] = []
    effective_status_counts: dict[str, int] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = str(task.get("status") or "")
        task_id = str(task.get("task_id") or "")
        repair = done_fixes_by_source.get(task_id)
        if status in {"failed", "cancelled"} and repair:
            task["repair_state"] = "repaired"
            task["repair_task_id"] = repair.get("task_id")
            task["display_status"] = "done"
            task["display_label"] = "repaired"
            repaired_ids.append(task_id)
            effective_status_counts["repaired"] = effective_status_counts.get("repaired", 0) + 1
            continue
        task["display_status"] = status
        if status in {"failed", "cancelled"}:
            unrepaired_failed_ids.append(task_id)
        effective_status_counts[status] = effective_status_counts.get(status, 0) + 1

    final_artifact_done = any(
        isinstance(artifact, dict) and "hermes_finalized" in str(artifact.get("summary") or "")
        for artifact in data.get("artifacts", [])
        if isinstance(artifact, dict)
    )
    active_statuses = {"open", "claimed", "running", "blocked", "review"}
    active_ids = [
        str(task.get("task_id") or "")
        for task in tasks
        if isinstance(task, dict) and str(task.get("status") or "") in active_statuses
    ]
    repair_summary = {
        "repaired_tasks": repaired_ids,
        "unrepaired_failed_tasks": unrepaired_failed_ids,
        "active_tasks": active_ids,
        "final_artifact_done": final_artifact_done,
        "complete": final_artifact_done and not unrepaired_failed_ids and not active_ids,
    }
    data["effective_status_counts"] = effective_status_counts
    data["repair_summary"] = repair_summary

    for chain in data.get("chains", []):
        if isinstance(chain, dict):
            chain["effective_status_counts"] = effective_status_counts
            chain["repair_summary"] = repair_summary

    return data


def quest_terminal_failure(data: dict[str, Any]) -> dict[str, Any]:
    repair = data.get("repair_summary") if isinstance(data, dict) else None
    if not isinstance(repair, dict):
        return {"terminal": False, "reason": None, "failed_tasks": []}
    failed = [
        str(task_id)
        for task_id in repair.get("unrepaired_failed_tasks", [])
        if str(task_id or "").strip()
    ]
    active = [
        str(task_id)
        for task_id in repair.get("active_tasks", [])
        if str(task_id or "").strip()
    ]
    final_done = bool(repair.get("final_artifact_done"))
    terminal = bool(failed and not active and not final_done)
    return {
        "terminal": terminal,
        "reason": "unrepaired_failed_tasks" if terminal else None,
        "failed_tasks": failed,
    }


def collect_provider_usage(workspace: Path, quest_chain_id: str) -> dict[str, Any]:
    payload_dir = workspace / "_runtime" / "guild-worker-agent"
    usage: dict[str, Any] = {
        "quest_chain_id": quest_chain_id,
        "provider_calls": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
        "entries": [],
    }
    if not payload_dir.is_dir():
        return usage

    for payload_path in sorted(payload_dir.glob("*-payload.json"), key=lambda item: item.stat().st_mtime):
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if str(payload.get("quest_chain_id") or "") != quest_chain_id:
            continue
        adapter_result = payload.get("adapter_result") or {}
        tokens = adapter_result.get("tokens") or {}
        attempts = adapter_result.get("attempts") or []
        provider_calls = len(attempts) if isinstance(attempts, list) and attempts else (1 if tokens else 0)
        total_tokens = int(tokens.get("total_tokens") or 0) if isinstance(tokens, dict) else 0
        cost_value = tokens.get("cost") if isinstance(tokens, dict) else None
        try:
            cost = float(cost_value or 0)
        except (TypeError, ValueError):
            cost = 0.0
        entry = {
            "task_id": payload.get("task_id"),
            "profile": payload.get("profile"),
            "adapter": payload.get("adapter"),
            "provider": payload.get("provider") or adapter_result.get("ammo"),
            "transport": adapter_result.get("transport"),
            "model": payload.get("model") or (attempts[0].get("model") if isinstance(attempts, list) and attempts and isinstance(attempts[0], dict) else None),
            "ok": payload.get("ok"),
            "blocked_reason": payload.get("blocked_reason") or adapter_result.get("blocked_reason"),
            "provider_calls": provider_calls,
            "total_tokens": total_tokens,
            "cost": cost,
        }
        usage["entries"].append(entry)
        usage["provider_calls"] += provider_calls
        usage["total_tokens"] += total_tokens
        usage["total_cost"] += cost
    return usage


def launch_hidden_worker_session(
    *,
    workspace: Path,
    powershell_exe: str,
    quest_chain_id: str,
    profile: str,
    adapter: str,
    db_path: str,
    interval_seconds: str,
    provider: Any = None,
    model: Any = None,
    capability: Any = None,
    dry_run: bool = False,
    once: bool = False,
) -> dict[str, Any]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    session_id = f"{safe_session_part(quest_chain_id)}-{safe_session_part(profile)}-{stamp}-{uuid.uuid4().hex[:6]}"
    session_dir = workspace / "_runtime" / "guild-worker-agent" / "terminal-sessions" / session_id
    stdout_path = session_dir / "stdout.log"
    stderr_path = session_dir / "stderr.log"
    loop_path = session_dir / "worker-loop.ps1"
    metadata_path = session_dir / "session.json"
    process: subprocess.Popen[str] | None = None

    metadata: dict[str, Any] = {
        "launched": not dry_run,
        "dry_run": dry_run,
        "visible": False,
        "session_id": session_id,
        "profile": profile,
        "agent_id": profile,
        "adapter": adapter,
        "provider": provider or "",
        "model": model or "",
        "capability": capability or "",
        "quest_chain_id": quest_chain_id,
        "interval_seconds": int(interval_seconds),
        "once": once,
        "process_id": None,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "metadata_path": str(metadata_path),
        "loop_script": str(loop_path),
    }
    if dry_run:
        return metadata

    session_dir.mkdir(parents=True, exist_ok=True)
    provider_line = f"    $workerArgs.Provider = {ps_quote(provider)}" if provider else ""
    model_line = f"    $workerArgs.Model = {ps_quote(model)}" if model else ""
    capability_line = f"    $workerArgs.Capability = {ps_quote(capability)}" if capability else ""
    db_line = f"    $workerArgs.DbPath = {ps_quote(db_path)}" if db_path else ""
    loop_script = f"""
Remove-Module PSReadLine -Force -ErrorAction SilentlyContinue
Set-Location -LiteralPath {ps_quote(workspace)}
Write-Host 'Guild worker session: {profile}'
Write-Host 'Quest chain: {quest_chain_id}'
Write-Host 'Adapter: {adapter}'
if ({ps_quote(capability)}) {{ Write-Host ('Capability: ' + {ps_quote(capability)}) }}
if ({ps_quote(provider)}) {{ Write-Host ('Preferred ammo: ' + {ps_quote(provider)}) }}
Write-Host 'This session is shown in the dashboard Worker Terminals tab.'
$idleCount = 0
while ($true) {{
    $workerArgs = @{{
        Profile = {ps_quote(profile)}
        Adapter = {ps_quote(adapter)}
        QuestChainId = {ps_quote(quest_chain_id)}
        Once = $true
        Json = $true
    }}
{provider_line}
{model_line}
{capability_line}
{db_line}
    $result = .\\scripts\\run-guild-worker-agent.ps1 @workerArgs
    if ($LASTEXITCODE -ne 0) {{
        Write-Host ''
        Write-Host ('[{{0}}] worker tick failed.' -f (Get-Date -Format 'HH:mm:ss'))
    }}
    if ($result) {{
        $parsed = $result | ConvertFrom-Json
        if ($parsed.claimed) {{
            $idleCount = 0
            Write-Host ''
            Write-Host ('[{{0}}] processing blackboard task' -f (Get-Date -Format 'HH:mm:ss'))
            Write-Host ('claimed: {{0}}' -f $parsed.task_id)
            Write-Host ('adapter result: ok={{0}} blocked={{1}}' -f $parsed.adapter_result.ok, $parsed.adapter_result.blocked_reason)
            Write-Host ('status update: {{0}}' -f $parsed.status_update.status)
        }} else {{
            $idleCount += 1
            if ($idleCount -eq 1) {{
                Write-Host ''
                Write-Host ('[{{0}}] idle: waiting for claimable task' -f (Get-Date -Format 'HH:mm:ss'))
            }}
        }}
    }}
    $exportArgs = @{{
        QuestChainId = {ps_quote(quest_chain_id)}
        IncludeArtifacts = $true
    }}
{db_line.replace("$workerArgs", "$exportArgs")}
    .\\scripts\\export-guild-dashboard.ps1 @exportArgs | Out-Null
    if ({'$true' if once else '$false'}) {{ break }}
    Start-Sleep -Seconds {int(interval_seconds)}
}}
""".strip()
    loop_path.write_text(loop_script, encoding="utf-8")
    stdout_handle = stdout_path.open("a", encoding="utf-8", errors="replace")
    stderr_handle = stderr_path.open("a", encoding="utf-8", errors="replace")
    try:
        process = subprocess.Popen(
            [
                powershell_exe,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(loop_path),
            ],
            cwd=workspace,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()
    metadata["process_id"] = process.pid if process else None
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


class GuildDashboardServer(SimpleHTTPRequestHandler):
    server_version = "GuildDashboardServer/0.1"

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    @property
    def workspace(self) -> Path:
        return Path(self.server.workspace)  # type: ignore[attr-defined]

    @property
    def python_exe(self) -> str:
        return str(self.server.python_exe)  # type: ignore[attr-defined]

    @property
    def db_path(self) -> str:
        return str(self.server.db_path)  # type: ignore[attr-defined]

    def send_json(self, value: Any, status: int = 200) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def run_cmd(self, args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        return subprocess.run(
            args,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json(
                {
                    "ok": True,
                    "service": "guild-dashboard",
                    "version": "0.3",
                    "capabilities": ["dashboard", "provider_lab", "demo_status"],
                    "workspace": str(self.workspace),
                    "db_path": self.db_path,
                }
            )
            return
        if parsed.path == "/api/dashboard":
            query = urllib.parse.parse_qs(parsed.query)
            quest_chain_id = query.get("quest_chain_id", ["demo-even-random-app"])[0]
            self.handle_dashboard(quest_chain_id)
            return
        if parsed.path == "/api/provider-lab/config":
            self.handle_provider_lab_config()
            return
        if parsed.path == "/api/demo/status":
            query = urllib.parse.parse_qs(parsed.query)
            quest_chain_id = query.get("quest_chain_id", [""])[0]
            self.handle_demo_status(quest_chain_id)
            return
        if parsed.path == "/api/dev/mtime":
            html_path = self.workspace / "docs" / "incubation" / "guild-dashboard.html"
            mtime = html_path.stat().st_mtime if html_path.exists() else 0
            self.send_json({"mtime": mtime})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        body: dict[str, Any] = {}
        try:
            body = self.read_json_body()
            append_event_log(
                self.workspace,
                "http_post_start",
                {
                    "path": parsed.path,
                    "quest_chain_id": body.get("quest_chain_id"),
                    "adapter": body.get("adapter"),
                    "profiles": body.get("profiles"),
                },
            )
            if parsed.path == "/api/quest/manual":
                self.handle_manual_quest(body)
                return
            if parsed.path == "/api/hermes/quest":
                self.handle_hermes_quest(body)
                return
            if parsed.path == "/api/hermes/finalize":
                self.handle_hermes_finalize(body)
                return
            if parsed.path == "/api/quest/stop":
                self.handle_quest_stop(body)
                return
            if parsed.path == "/api/task/retry-blocked":
                self.handle_task_retry_blocked(body)
                return
            if parsed.path == "/api/wake":
                self.handle_wake(body)
                return
            if parsed.path == "/api/provider-lab/save-secret":
                self.handle_provider_lab_save_secret(body)
                return
            if parsed.path == "/api/provider-lab/list-models":
                self.handle_provider_lab_list_models(body)
                return
            if parsed.path == "/api/provider-lab/test":
                self.handle_provider_lab_test(body)
                return
            if parsed.path == "/api/provider-lab/quick-add":
                self.handle_provider_lab_quick_add(body)
                return
            if parsed.path == "/api/provider-lab/save-combo":
                self.handle_provider_lab_save_combo(body)
                return
            if parsed.path == "/api/hermes/plan-preview":
                self.handle_hermes_plan_preview(body)
                return
            self.send_json({"ok": False, "error": "not_found"}, status=404)
        except Exception as exc:  # Keep local demo errors visible to the UI.
            append_event_log(
                self.workspace,
                "http_post_error",
                {
                    "path": parsed.path,
                    "quest_chain_id": body.get("quest_chain_id"),
                    "adapter": body.get("adapter"),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_dashboard(self, quest_chain_id: str) -> None:
        dashboard = self.export_dashboard(quest_chain_id)
        self.send_json({"ok": True, "dashboard": dashboard})

    def handle_task_retry_blocked(self, body: dict[str, Any]) -> None:
        task_id = str(body.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("task_id is required")
        quest_chain_id = str(body.get("quest_chain_id") or "").strip()
        completed = self.run_cmd(
            [
                self.python_exe,
                str(self.workspace / "_runtime" / "flock" / "worker_team_prototype.py"),
                "--db",
                self.db_path,
                "retry-blocked",
                task_id,
            ]
        )
        result = parse_json_object(completed.stdout)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or f"retry-blocked failed for {task_id}")
        if not result.get("reopened"):
            self.send_json({"ok": False, "retry": result}, status=409)
            return
        append_event_log(
            self.workspace,
            "task_retry_blocked",
            {
                "quest_chain_id": quest_chain_id or None,
                "task_id": task_id,
                "previous_blocked_reason": result.get("previous_blocked_reason"),
            },
        )
        dashboard = self.export_dashboard(quest_chain_id) if quest_chain_id else None
        self.send_json({"ok": True, "retry": result, "dashboard": dashboard})

    def handle_demo_status(self, quest_chain_id: str) -> None:
        dashboard = self.export_dashboard(quest_chain_id) if quest_chain_id else None
        self.send_json(
            {
                "ok": True,
                "quest_chain_id": quest_chain_id,
                "db_path": self.db_path,
                "dashboard": dashboard,
                "logs": read_demo_logs(self.workspace, quest_chain_id),
                "runtime": read_runtime_snapshots(self.workspace, quest_chain_id),
            }
        )

    def export_dashboard(self, quest_chain_id: str) -> dict[str, Any]:
        prototype = self.workspace / "_runtime" / "flock" / "worker_team_prototype.py"
        args = [
            self.python_exe,
            str(prototype),
            "--db",
            self.db_path,
            "dashboard",
            "--quest-chain-id",
            quest_chain_id,
            "--include-tasks",
            "--include-artifacts",
        ]
        completed = self.run_cmd(args)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or "dashboard export failed")
        data = json.loads(completed.stdout)
        data = enrich_repaired_dashboard(data)
        data["provider_usage"] = collect_provider_usage(self.workspace, quest_chain_id)
        out_dir = self.workspace / "_runtime" / "dashboard"
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            write_json_atomic(out_dir / "guild-dashboard.json", data)
        except PermissionError as exc:
            append_event_log(
                self.workspace,
                "dashboard_snapshot_write_skipped",
                {
                    "quest_chain_id": quest_chain_id,
                    "reason": "permission_error",
                    "error": str(exc),
                },
            )
        return data

    def handle_manual_quest(self, body: dict[str, Any]) -> None:
        title = str(body.get("title") or "Manual guild quest").strip()
        request = str(body.get("request") or "").strip()
        if not request:
            raise ValueError("request is required")
        slug = slugify(str(body.get("quest_chain_id") or title))
        quest_chain_id = slug if slug.startswith("quest-") else f"quest-{slug}"
        allowed_files = str(body.get("allowed_files") or "").strip()
        adapter = str(body.get("adapter") or "local-dry-run").strip()
        runtime = load_guild_runtime_config(self.workspace)

        quest_workspace = create_quest_workspace(self.workspace, quest_chain_id, title, request)
        workspace_glob = f"guild-workspaces/{quest_chain_id}/**"
        effective_allowed_files = join_allowed_files(workspace_glob, allowed_files)

        plan, events, wake_profiles = build_manual_plan(
            quest_chain_id,
            title,
            request,
            effective_allowed_files,
            quest_workspace,
            runtime,
        )

        for task in plan:
            self.create_task(task)
        self.run_cmd(
            [
                self.python_exe,
                str(self.workspace / "_runtime" / "flock" / "worker_team_prototype.py"),
                "--db",
                self.db_path,
                "unlock-ready",
                "--limit",
                "50",
            ]
        )
        dashboard = self.export_dashboard(quest_chain_id)
        append_event_log(
            self.workspace,
            "quest_manual_created",
            {
                "quest_chain_id": quest_chain_id,
                "adapter": adapter,
                "provider_mode": "local-demo" if adapter in {"local-dry-run", "local-file-writer"} else "provider-adapter",
                "wake_profiles": wake_profiles,
                "task_count": len(plan),
            },
        )
        self.send_json(
            {
                "ok": True,
                "quest_chain_id": quest_chain_id,
                "adapter": adapter,
                "router_mode": "manual-router-v0",
                "provider_mode": "local-demo" if adapter in {"local-dry-run", "local-file-writer"} else "provider-adapter",
                "workspace_path": str(quest_workspace.relative_to(self.workspace)),
                "events": events,
                "wake_profiles": wake_profiles,
                "tasks": plan,
                "dashboard": dashboard,
            }
        )

    def handle_hermes_quest(self, body: dict[str, Any]) -> None:
        title = str(body.get("title") or "Hermes guild quest").strip()
        request = str(body.get("request") or "").strip()
        if not request:
            raise ValueError("request is required")
        slug = slugify(str(body.get("quest_chain_id") or title))
        quest_chain_id = slug if slug.startswith("quest-") else f"quest-{slug}"
        allowed_files = str(body.get("allowed_files") or "").strip()
        adapter = str(body.get("adapter") or "opencode").strip()
        runtime = load_guild_runtime_config(self.workspace)

        planner = dict(body.get("planner") or {})
        if planner:
            planner = validate_dynamic_planner(planner, self.workspace, runtime)
        else:
            workspace_rel = Path("guild-workspaces") / quest_chain_id
            if adapter in {"auto-rank", "rank-auto", "auto", "auto-ammo"}:
                append_event_log(
                    self.workspace,
                    "hermes_planner_skipped",
                    {
                        "quest_chain_id": quest_chain_id,
                        "adapter": adapter,
                        "reason": "planner_skill_pack_for_auto_rank",
                    },
                )
                planner = build_skill_pack_planner(
                    self.workspace,
                    title=title,
                    request=request,
                    runtime=runtime,
                    fallback_reason="Hermes planner skipped for auto-rank to avoid unnecessary model spend.",
                )
            else:
                try:
                    planner = self.call_hermes_planner(
                        title=title,
                        request=request,
                        quest_chain_id=quest_chain_id,
                        workspace_path=workspace_rel.as_posix(),
                        adapter=adapter,
                        runtime=runtime,
                    )
                except Exception as exc:
                    append_event_log(
                        self.workspace,
                        "hermes_planner_fallback",
                        {
                            "quest_chain_id": quest_chain_id,
                            "adapter": adapter,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "fallback": "planner_skill_pack",
                        },
                    )
                    planner = build_skill_pack_planner(
                        self.workspace,
                        title=title,
                        request=request,
                        runtime=runtime,
                        fallback_reason=str(exc),
                    )

        planner_title = str(planner.get("title") or title).strip()
        planner_request = str(planner.get("request") or request).strip()
        quest_workspace = create_quest_workspace(
            self.workspace,
            quest_chain_id,
            planner_title,
            planner_request,
            planner=planner,
        )
        workspace_glob = f"guild-workspaces/{quest_chain_id}/**"
        effective_allowed_files = join_allowed_files(workspace_glob, allowed_files)

        plan, events, wake_profiles = build_dynamic_hermes_plan(
            quest_chain_id=quest_chain_id,
            title=planner_title,
            request=planner_request,
            allowed_files=effective_allowed_files,
            quest_workspace=quest_workspace,
            planner=planner,
            runtime=runtime,
        )

        for task in plan:
            self.create_task(task)
        self.run_cmd(
            [
                self.python_exe,
                str(self.workspace / "_runtime" / "flock" / "worker_team_prototype.py"),
                "--db",
                self.db_path,
                "unlock-ready",
                "--limit",
                "50",
            ]
        )
        dashboard = self.export_dashboard(quest_chain_id)
        append_event_log(
            self.workspace,
            "quest_hermes_created",
            {
                "quest_chain_id": quest_chain_id,
                "adapter": adapter,
                "provider_mode": "provider-adapter",
                "wake_profiles": wake_profiles,
                "task_count": len(plan),
                "hermes_provider": planner.get("_hermes_provider"),
                "hermes_model": planner.get("_hermes_model"),
            },
        )
        self.send_json(
            {
                "ok": True,
                "quest_chain_id": quest_chain_id,
                "adapter": adapter,
                "router_mode": "hermes-planner-v0",
                "provider_mode": "provider-adapter",
                "workspace_path": str(quest_workspace.relative_to(self.workspace)),
                "hermes": {
                    "provider": planner.get("_hermes_provider"),
                    "model": planner.get("_hermes_model"),
                    "summary": planner.get("summary"),
                    "fallback": planner.get("_fallback_reason"),
                },
                "events": events,
                "wake_profiles": wake_profiles,
                "tasks": plan,
                "dashboard": dashboard,
            }
        )

    def handle_hermes_plan_preview(self, body: dict[str, Any]) -> None:
        title = str(body.get("title") or "Hermes guild quest").strip()
        request = str(body.get("request") or "").strip()
        if not request:
            raise ValueError("request is required")
        slug = slugify(str(body.get("quest_chain_id") or title))
        quest_chain_id = slug if slug.startswith("quest-") else f"quest-{slug}"
        allowed_files = str(body.get("allowed_files") or "").strip()
        adapter = str(body.get("adapter") or "auto-ammo").strip()
        runtime = load_guild_runtime_config(self.workspace)
        workspace_rel = Path("guild-workspaces") / quest_chain_id
        planner = build_skill_pack_planner(
            self.workspace,
            title=title,
            request=request,
            runtime=runtime,
            fallback_reason="plan_preview",
        )
        planner = validate_dynamic_planner(planner, self.workspace, runtime)
        preview_workspace = self.workspace / workspace_rel
        workspace_glob = f"guild-workspaces/{quest_chain_id}/**"
        effective_allowed_files = join_allowed_files(workspace_glob, allowed_files)
        plan, events, wake_profiles = build_dynamic_hermes_plan(
            quest_chain_id=quest_chain_id,
            title=str(planner.get("title") or title),
            request=str(planner.get("request") or request),
            allowed_files=effective_allowed_files,
            quest_workspace=preview_workspace,
            planner=planner,
            runtime=runtime,
        )
        append_event_log(
            self.workspace,
            "hermes_plan_preview",
            {
                "quest_chain_id": quest_chain_id,
                "adapter": adapter,
                "template": planner.get("template"),
                "task_count": len(plan),
            },
        )
        self.send_json(
            {
                "ok": True,
                "quest_chain_id": quest_chain_id,
                "adapter": adapter,
                "router_mode": "hermes-planner-skill-pack-v0",
                "workspace_path": workspace_rel.as_posix(),
                "hermes": {
                    "summary": planner.get("summary"),
                    "template": planner.get("template"),
                    "fallback": planner.get("_fallback_reason"),
                },
                "events": events,
                "wake_profiles": wake_profiles,
                "planner": planner,
                "tasks": plan,
            }
        )

    def call_hermes_planner(
        self,
        *,
        title: str,
        request: str,
        quest_chain_id: str,
        workspace_path: str,
        adapter: str,
        runtime: dict[str, Any],
    ) -> dict[str, Any]:
        provider = os.environ.get("HERMES_GUILD_HERMES_PROVIDER", "openai-codex")
        model = os.environ.get("HERMES_GUILD_HERMES_MODEL", "gpt-5.5")
        tracks = runtime_module_tracks(runtime)
        track_lines = "\n".join(
            f"- Track {track['id']} writes {track['output_file']} with required_skill={track['skill']}"
            for track in tracks
        )
        prompt = f"""
You are Hermes, S-rank Guild manager for HermesGuildCore.
Return only compact JSON. No markdown.

Create a bounded worker plan for this UI quest.
Use this fixed runtime contract:
- quest_chain_id: {quest_chain_id}
- quest workspace: {workspace_path}
- workers may write only inside the quest workspace
- split into exactly {len(tracks)} parallel build tracks from runtime config
{track_lines}
- a reviewer worker performs join_review after configured worker outputs are done
- Hermes finalizer only validates reviewer outputs and writes final-artifact.json
- preferred worker adapter: {adapter}

User title:
{title}

User request:
{request}

Required JSON schema:
{{
  "ok": true,
  "title": "short quest title",
  "request": "cleaned user request",
  "summary": "one sentence manager summary",
  "tracks": [
    {{"id":"A","title":"Build track A","instruction":"specific worker instruction"}},
    {{"id":"B","title":"Build track B","instruction":"specific worker instruction"}},
    {{"id":"C","title":"Build track C","instruction":"specific worker instruction"}}
  ],
  "review_instruction": "specific reviewer instruction",
  "risks": []
}}
"""
        hermes_cli = resolve_hermes_cli(self.workspace)
        append_event_log(
            self.workspace,
            "hermes_planner_start",
            {
                "quest_chain_id": quest_chain_id,
                "provider": provider,
                "model": model,
                "hermes_cli": hermes_cli,
                "preferred_worker_adapter": adapter,
            },
        )
        args = [hermes_cli, "--provider", provider, "-m", model, "--ignore-rules", "-z", prompt]
        completed = self.run_cmd(args, timeout=120)
        append_event_log(
            self.workspace,
            "hermes_planner_done",
            {
                "quest_chain_id": quest_chain_id,
                "returncode": completed.returncode,
                "stdout_chars": len(completed.stdout or ""),
                "stderr_tail": tail_text(completed.stderr),
            },
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or "Hermes planner failed")
        text = (completed.stdout or "").strip()
        try:
            planner = extract_json_object(text)
        except ValueError as exc:
            raise RuntimeError(f"Hermes planner returned non-JSON output: {text[:1000]}") from exc
        if not planner.get("ok"):
            raise RuntimeError(f"Hermes planner returned ok=false: {planner}")
        planner = validate_dynamic_planner(planner, self.workspace, runtime)
        planner["_hermes_provider"] = provider
        planner["_hermes_model"] = model
        return planner

    def handle_hermes_finalize(self, body: dict[str, Any]) -> None:
        quest_chain_id = str(body.get("quest_chain_id") or "").strip()
        if not quest_chain_id:
            raise ValueError("quest_chain_id is required")
        quest_workspace = self.workspace / "guild-workspaces" / quest_chain_id
        if not quest_workspace.is_dir():
            raise ValueError(f"missing quest workspace: {quest_workspace}")

        dashboard = self.export_dashboard(quest_chain_id)
        tasks = dashboard.get("tasks") or []
        runtime = load_guild_runtime_config(self.workspace)
        build_tasks = fan_in_tasks_for_review(tasks)
        if not build_tasks:
            self.send_json(
                {
                    "ok": False,
                    "ready": False,
                    "reason": "waiting_for_worker_outputs",
                    "dashboard": dashboard,
                },
                status=409,
            )
            return
        tracks = planner_tracks_from_tasks(build_tasks, runtime)

        review_tasks = [task for task in tasks if str(task.get("task_type") or "") == "join_review"]
        if not review_tasks:
            raise ValueError("missing join_review task")
        review_task = review_tasks[0]

        repair = self.ensure_fix_tasks_for_failed_or_missing_modules(
            quest_chain_id=quest_chain_id,
            quest_workspace=quest_workspace,
            tasks=tasks,
            build_tasks=build_tasks,
            review_task=review_task,
            runtime=runtime,
        )
        if repair["created"] or repair["waiting"]:
            dashboard = self.export_dashboard(quest_chain_id)
            self.send_json(
                {
                    "ok": True,
                    "ready": False,
                    "reason": "repair_tasks_pending",
                    "repair": repair,
                    "dashboard": dashboard,
                }
            )
            return

        final_config = runtime.get("final_assembly") or {}
        review_path = quest_workspace / str(final_config.get("review_file") or "review.md")
        final_path = quest_workspace / str(final_config.get("summary_file") or "final-summary.md")
        artifact_path = quest_workspace / str(final_config.get("artifact_file") or "final-artifact.json")
        final_paths = [review_path, final_path, artifact_path]
        if review_task.get("status") == "done" and all(path.is_file() for path in final_paths):
            validations = validate_final_outputs(self.workspace, quest_workspace, tracks, final_paths)
            if all(item["ok"] for item in validations):
                self.send_json(
                    {
                        "ok": True,
                        "ready": True,
                        "already_done": True,
                        "validations": validations,
                        "dashboard": dashboard,
                    }
                )
                return

        review_status = str(review_task.get("status") or "")
        if review_status in {"failed", "cancelled"}:
            append_event_log(
                self.workspace,
                "finalize_review_terminal",
                {
                    "quest_chain_id": quest_chain_id,
                    "review_task_id": review_task.get("task_id"),
                    "review_status": review_status,
                },
            )
            self.send_json(
                {
                    "ok": True,
                    "ready": False,
                    "terminal": True,
                    "reason": "join_review_failed",
                    "review_task_id": review_task.get("task_id"),
                    "review_status": review_status,
                    "failure": quest_terminal_failure(dashboard),
                    "dashboard": dashboard,
                }
            )
            return

        if review_status != "done":
            append_event_log(
                self.workspace,
                "finalize_waiting_review",
                {
                    "quest_chain_id": quest_chain_id,
                    "review_task_id": review_task.get("task_id"),
                    "review_status": review_status,
                },
            )
            self.send_json(
                {
                    "ok": True,
                    "ready": False,
                    "reason": "waiting_for_join_review_worker",
                    "review_task_id": review_task.get("task_id"),
                    "review_status": review_task.get("status"),
                    "dashboard": dashboard,
                }
            )
            return

        summaries: list[tuple[str, str]] = []
        missing: list[str] = []
        for track in tracks:
            path = quest_workspace / str(track["output_file"])
            if not path.is_file():
                missing.append(path.name)
                continue
            summaries.append((path.name, path.read_text(encoding="utf-8", errors="replace").strip()))
        if missing:
            self.send_json(
                {
                    "ok": False,
                    "ready": False,
                    "reason": f"missing worker files: {', '.join(missing)}",
                    "dashboard": dashboard,
                },
                status=409,
            )
            return

        missing_review_outputs = [
            str(path.relative_to(self.workspace))
            for path in [review_path, final_path]
            if not path.is_file()
        ]
        if missing_review_outputs:
            self.send_json(
                {
                    "ok": False,
                    "ready": False,
                    "reason": "missing_join_review_outputs",
                    "missing": missing_review_outputs,
                    "dashboard": dashboard,
                },
                status=409,
            )
            return

        pre_artifact_validations = validate_final_outputs(self.workspace, quest_workspace, tracks, [review_path, final_path])
        if not all(item["ok"] for item in pre_artifact_validations):
            self.send_json(
                {
                    "ok": False,
                    "ready": False,
                    "reason": "final_output_validation_failed",
                    "validations": pre_artifact_validations,
                    "dashboard": dashboard,
                },
                status=409,
            )
            return

        payload_dir = self.workspace / "_runtime" / "dashboard"
        payload_dir.mkdir(parents=True, exist_ok=True)
        payload_path = payload_dir / f"{quest_chain_id}-hermes-finalize.json"
        payload = {
            "ok": True,
            "mode": "hermes_finalize_v1",
            "quest_chain_id": quest_chain_id,
            "files_changed": [
                str(artifact_path.relative_to(self.workspace)),
            ],
            "summary": "Hermes verified configured worker and reviewer outputs, then wrote the final artifact.",
            "validations": pre_artifact_validations,
            "module_tracks": [
                {
                    "index": track["index"],
                    "skill": track["skill"],
                    "output_file": track["output_file"],
                }
                for track in tracks
            ],
        }
        artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        validations = validate_final_outputs(self.workspace, quest_workspace, tracks, [review_path, final_path, artifact_path])
        payload["validations"] = validations
        artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.publish_artifact(
            task_id=str(review_task["task_id"]),
            artifact_type=str(review_task.get("output_artifact") or "integration_report"),
            producer_agent_id="hermes-codex",
            summary=f"hermes_finalized_{quest_chain_id}",
            payload_path=payload_path,
        )
        telegram = self.send_telegram_report(
            "\n".join(
                [
                    "Hermes Guild quest complete",
                    f"Quest: {quest_chain_id}",
                    "Workers: selected from config/guild/guild-runtime.json",
                    f"Files: {review_path.name}, {final_path.name}, {artifact_path.name}",
                    f"Workspace: guild-workspaces/{quest_chain_id}",
                ]
            )
        )
        dashboard = self.export_dashboard(quest_chain_id)
        append_event_log(
            self.workspace,
            "finalize_done",
            {
                "quest_chain_id": quest_chain_id,
                "files": payload["files_changed"],
                "telegram_ok": telegram.get("ok") if isinstance(telegram, dict) else None,
            },
        )
        self.send_json(
            {
                "ok": True,
                "ready": True,
                "quest_chain_id": quest_chain_id,
                "files": payload["files_changed"],
                "telegram": telegram,
                "dashboard": dashboard,
            }
        )

    def handle_quest_stop(self, body: dict[str, Any]) -> None:
        quest_chain_id = str(body.get("quest_chain_id") or "").strip()
        if not quest_chain_id:
            raise ValueError("quest_chain_id is required")
        write_quest_stop_marker(self.workspace, quest_chain_id)
        cancelled = cancel_quest_tasks(Path(self.db_path), quest_chain_id)
        append_event_log(
            self.workspace,
            "quest_stop_requested",
            {
                "quest_chain_id": quest_chain_id,
                "cancelled": cancelled,
            },
        )
        self.send_json(
            {
                "ok": True,
                "quest_chain_id": quest_chain_id,
                "cancelled": cancelled,
            }
        )

    def ensure_fix_tasks_for_failed_or_missing_modules(
        self,
        *,
        quest_chain_id: str,
        quest_workspace: Path,
            tasks: list[dict[str, Any]],
            build_tasks: list[dict[str, Any]],
            review_task: dict[str, Any],
            runtime: dict[str, Any],
    ) -> dict[str, Any]:
        fix_tasks = [task for task in tasks if str(task.get("task_type") or "") == "fix"]
        fixes_by_source: dict[str, list[dict[str, Any]]] = {}
        for task in fix_tasks:
            source = str(task.get("generated_from") or "")
            if source:
                fixes_by_source.setdefault(source, []).append(task)

        created: list[str] = []
        waiting: list[str] = []
        review_dependencies: list[str] = []
        tracks = runtime_module_tracks(runtime)

        for build_task in sorted(build_tasks, key=lambda item: int(item.get("sequence_no") or 0)):
            task_id = str(build_task.get("task_id") or "")
            track = module_track_for_task(build_task, tracks)
            if not track:
                continue
            module_index = int(track["index"])
            output_file = str(track["output_file"])
            expected_file = quest_workspace / output_file
            status = str(build_task.get("status") or "")
            if status != "done" and status not in {"failed", "cancelled"}:
                waiting.append(task_id)
                review_dependencies.append(task_id)
                continue

            grounding_only_failure = (
                status in {"failed", "cancelled"}
                and expected_file.is_file()
                and task_failed_only_by_grounding_gate(self.workspace, build_task)
            )
            if grounding_only_failure:
                append_event_log(
                    self.workspace,
                    "finalize_accept_existing_grounded_file",
                    {
                        "quest_chain_id": quest_chain_id,
                        "task_id": task_id,
                        "output_file": output_file,
                        "reason": "failed_only_by_grounding_gate",
                    },
                )
                review_dependencies.append(task_id)
                continue

            needs_fix = status in {"failed", "cancelled"} or not expected_file.is_file()

            if not needs_fix:
                review_dependencies.append(task_id)
                continue

            existing = fixes_by_source.get(task_id, [])
            max_fix_rounds = int((runtime.get("review") or {}).get("max_fix_rounds") or 3)
            done_fix = next((task for task in existing if task.get("status") == "done"), None)
            if done_fix:
                review_dependencies.append(str(done_fix.get("task_id")))
                continue

            active_fix = next(
                (
                    task
                    for task in existing
                    if task.get("status") in {"open", "claimed", "running", "blocked"}
                ),
                None,
            )
            if active_fix:
                waiting.append(str(active_fix.get("task_id")))
                review_dependencies.append(str(active_fix.get("task_id")))
                continue

            fix_round = len(existing) + 1
            if fix_round > max_fix_rounds:
                waiting.append(f"{task_id}:max_fix_rounds_reached")
                review_dependencies.append(task_id)
                continue
            fix_task_id = f"{task_id}-fix-{fix_round}"
            skill = str(track.get("skill") or build_task.get("required_skill") or "general")
            reason = "failed build task" if status != "done" else f"missing {output_file}"
            self.create_task(
                {
                    "task_id": fix_task_id,
                    "task_type": "fix",
                    "required_rank": str(build_task.get("required_rank") or "C"),
                    "required_skill": skill,
                    "owner_area": "repair",
                    "status": "open",
                    "plan_review_status": "approved",
                    "quest_chain_id": quest_chain_id,
                    "sequence_no": int(build_task.get("sequence_no") or module_index) + 10 + fix_round,
                    "depends_on": [],
                    "output_artifact": f"fix_result_{module_index}",
                    "allowed_files": f"guild-workspaces/{quest_chain_id}/**",
                    "generated_from": task_id,
                    "fix_round": fix_round,
                    "max_fix_rounds": max_fix_rounds,
                    "title": f"Fix module {module_index}: {build_task.get('title') or task_id}",
                    "request": "\n".join(
                        [
                            f"Repair module {module_index} after Hermes meeting detected: {reason}.",
                            f"Quest workspace: guild-workspaces/{quest_chain_id}",
                            f"Write or correct {output_file} inside the quest workspace.",
                            "Keep the fix bounded to this module.",
                            "Return artifact JSON listing the file you wrote.",
                        ]
                    ),
                }
            )
            created.append(fix_task_id)
            review_dependencies.append(fix_task_id)

        if created or waiting:
            self.create_task(
                {
                    "task_id": str(review_task.get("task_id")),
                    "task_type": "join_review",
                    "required_rank": str(review_task.get("required_rank") or "B"),
                    "required_skill": str(review_task.get("required_skill") or "integration_review"),
                    "owner_area": str(review_task.get("owner_area") or "review"),
                    "status": "blocked",
                    "plan_review_status": "approved",
                    "quest_chain_id": quest_chain_id,
                    "sequence_no": int(review_task.get("sequence_no") or 5),
                    "depends_on": review_dependencies,
                    "output_artifact": str(review_task.get("output_artifact") or "integration_report"),
                    "allowed_files": f"guild-workspaces/{quest_chain_id}/**",
                    "title": str(review_task.get("title") or f"Review: {quest_chain_id}"),
                    "request": "\n".join(
                        [
                            "Hermes meeting/review waits for original module tasks and repair tasks.",
                            f"Quest workspace: guild-workspaces/{quest_chain_id}",
                            "When all dependencies are done, write review.md and final-summary.md.",
                        ]
                    ),
                }
            )

        return {"created": created, "waiting": waiting, "review_dependencies": review_dependencies}

    def create_task(self, task: dict[str, Any]) -> None:
        prototype = self.workspace / "_runtime" / "flock" / "worker_team_prototype.py"
        args = [
            self.python_exe,
            str(prototype),
            "--db",
            self.db_path,
            "create-task",
            "--task-id",
            task["task_id"],
            "--task-type",
            task["task_type"],
            "--required-rank",
            task["required_rank"],
            "--required-skill",
            task["required_skill"],
            "--owner-area",
            task["owner_area"],
            "--status",
            task["status"],
            "--plan-review-status",
            task["plan_review_status"],
            "--quest-chain-id",
            task["quest_chain_id"],
            "--sequence-no",
            str(task["sequence_no"]),
            "--output-artifact",
            task["output_artifact"],
            "--title",
            task["title"],
            "--request",
            task["request"],
        ]
        if task.get("depends_on"):
            args.extend(["--depends-on", ",".join(task["depends_on"])])
        if task.get("allowed_files"):
            args.extend(["--allowed-files", task["allowed_files"]])
        if task.get("generated_from"):
            args.extend(["--generated-from", task["generated_from"]])
        if task.get("source_artifact"):
            args.extend(["--source-artifact", task["source_artifact"]])
        if task.get("fix_round") is not None:
            args.extend(["--fix-round", str(task["fix_round"])])
        if task.get("max_fix_rounds") is not None:
            args.extend(["--max-fix-rounds", str(task["max_fix_rounds"])])
        if task["plan_review_status"] == "not_required":
            args.append("--plan-review-not-required")
        completed = self.run_cmd(args)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or f"create-task failed for {task['task_id']}")

    def publish_artifact(
        self,
        *,
        task_id: str,
        artifact_type: str,
        producer_agent_id: str,
        summary: str,
        payload_path: Path,
    ) -> None:
        completed = self.run_cmd(
            [
                self.python_exe,
                str(self.workspace / "_runtime" / "flock" / "worker_team_prototype.py"),
                "--db",
                self.db_path,
                "publish-artifact",
                "--task-id",
                task_id,
                "--artifact-type",
                artifact_type,
                "--producer-agent-id",
                producer_agent_id,
                "--summary",
                summary,
                "--payload-json-file",
                str(payload_path),
            ]
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or f"publish-artifact failed for {task_id}")

    def set_task_status(self, task_id: str, status: str) -> None:
        completed = self.run_cmd(
            [
                self.python_exe,
                str(self.workspace / "_runtime" / "flock" / "worker_team_prototype.py"),
                "--db",
                self.db_path,
                "set-status",
                task_id,
                status,
            ]
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or f"set-status failed for {task_id}")

    def send_telegram_report(self, text: str) -> dict[str, Any]:
        script = self.workspace / "scripts" / "send-telegram-home.ps1"
        if not script.is_file():
            return {"ok": False, "skipped": True, "reason": "missing_send_telegram_script"}
        try:
            log_dir = self.workspace / "_runtime" / "dashboard"
            log_dir.mkdir(parents=True, exist_ok=True)
            stdout_path = log_dir / "telegram-finalize.out.log"
            stderr_path = log_dir / "telegram-finalize.err.log"
            env = os.environ.copy()
            env.pop("PYTHONHOME", None)
            env.pop("PYTHONPATH", None)
            stdout_handle = stdout_path.open("a", encoding="utf-8")
            stderr_handle = stderr_path.open("a", encoding="utf-8")
            process = subprocess.Popen(
                [
                    resolve_powershell_exe(),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-Text",
                    text,
                    "-TimeoutSec",
                    "30",
                ],
                cwd=self.workspace,
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=env,
            )
            stdout_handle.close()
            stderr_handle.close()
            return {
                "ok": True,
                "queued": True,
                "pid": process.pid,
                "stdout_log": str(stdout_path.relative_to(self.workspace)),
                "stderr_log": str(stderr_path.relative_to(self.workspace)),
            }
        except Exception as exc:
            return {"ok": False, "skipped": False, "reason": str(exc)}

    def handle_wake(self, body: dict[str, Any]) -> None:
        quest_chain_id = str(body.get("quest_chain_id") or "").strip()
        if not quest_chain_id:
            raise ValueError("quest_chain_id is required")
        adapter = str(body.get("adapter") or "local-dry-run").strip()
        runtime = load_guild_runtime_config(self.workspace)
        profiles = body.get("profiles") or schedule_quest_wake_profiles(self.workspace, runtime)
        include_hermes_terminal = bool(body.get("include_hermes_terminal"))
        visible_terminals = bool(body.get("visible_terminals"))
        if include_hermes_terminal:
            profiles = [profile for profile in profiles if str(profile).lower() != "hermes"]
        dry_run = bool(body.get("dry_run"))
        interval_seconds = str(int(body.get("interval_seconds") or 2))
        worker_routes = resolve_worker_routes(adapter, profiles, runtime, self.workspace)
        worker_adapters = [str(route["adapter"]) for route in worker_routes]
        append_event_log(
            self.workspace,
            "wake_start",
            {
                "quest_chain_id": quest_chain_id,
                "adapter": adapter,
                "profiles": profiles,
                "worker_adapters": worker_adapters,
                "worker_routes": worker_routes,
                "include_hermes_terminal": include_hermes_terminal,
                "dry_run": dry_run,
            },
        )
        launched = []
        powershell_exe = resolve_powershell_exe()
        port = int(self.server.server_port)  # type: ignore[attr-defined]
        for index, profile in enumerate(profiles):
            route = worker_routes[index]
            worker_adapter = str(route["adapter"])
            if visible_terminals:
                args = [
                    powershell_exe,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(self.workspace / "scripts" / "start-guild-worker-terminal.ps1"),
                    "-QuestChainId",
                    quest_chain_id,
                    "-Profile",
                    str(profile),
                    "-Adapter",
                    worker_adapter,
                    "-IntervalSeconds",
                    interval_seconds,
                    "-DbPath",
                    self.db_path,
                    "-Json",
                    "-Visible",
                ]
                if route.get("provider"):
                    args.extend(["-Provider", str(route["provider"])])
                if route.get("model"):
                    args.extend(["-Model", str(route["model"])])
                if route.get("capability"):
                    args.extend(["-Capability", str(route["capability"])])
                if dry_run:
                    args.append("-DryRun")
                completed = self.run_cmd(args)
                terminal_session = parse_json_object(completed.stdout)
                returncode = completed.returncode
                stdout = completed.stdout
                stderr = completed.stderr
            else:
                terminal_session = launch_hidden_worker_session(
                    workspace=self.workspace,
                    powershell_exe=powershell_exe,
                    quest_chain_id=quest_chain_id,
                    profile=str(profile),
                    adapter=worker_adapter,
                    db_path=self.db_path,
                    interval_seconds=interval_seconds,
                    provider=route.get("provider"),
                    model=route.get("model"),
                    capability=route.get("capability"),
                    dry_run=dry_run,
                )
                returncode = 0
                stdout = json.dumps(terminal_session, ensure_ascii=False)
                stderr = ""
            append_event_log(
                self.workspace,
                "wake_profile",
                {
                    "quest_chain_id": quest_chain_id,
                    "profile": profile,
                    "adapter": worker_adapter,
                    "provider": route.get("provider"),
                    "capability": route.get("capability"),
                    "route_reason": route.get("reason"),
                    "visible": visible_terminals,
                    "session_id": terminal_session.get("session_id"),
                    "process_id": terminal_session.get("process_id"),
                    "returncode": returncode,
                    "stdout_tail": tail_text(stdout),
                    "stderr_tail": tail_text(stderr),
                },
            )
            launched.append(
                {
                    "profile": profile,
                    "adapter": worker_adapter,
                    "provider": route.get("provider"),
                    "capability": route.get("capability"),
                    "route_reason": route.get("reason"),
                    "ok": returncode == 0,
                    "visible": visible_terminals,
                    "terminal_session": terminal_session,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
        if include_hermes_terminal:
            args = [
                powershell_exe,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.workspace / "scripts" / "start-guild-finalizer-terminal.ps1"),
                "-QuestChainId",
                quest_chain_id,
                "-Port",
                str(port),
                "-IntervalSeconds",
                interval_seconds,
            ]
            completed = self.run_cmd(args)
            launched.append(
                {
                    "profile": "hermes-finalizer",
                    "adapter": "hermes",
                    "ok": completed.returncode == 0,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
        time.sleep(0.3)
        dashboard = self.export_dashboard(quest_chain_id)
        self.send_json(
            {
                "ok": True,
                "quest_chain_id": quest_chain_id,
                "adapter": adapter,
                "worker_adapters": worker_adapters,
                "worker_routes": worker_routes,
                "launched": launched,
                "dashboard": dashboard,
            }
        )

    def handle_provider_lab_config(self) -> None:
        config = load_guild_provider_config(self.workspace)
        env_keys = allowed_provider_env_keys(config["transports"])
        self.send_json(
            {
                "ok": True,
                "transports": config["transports"],
                "cartridges": config["cartridges"],
                "capabilities": config["capabilities"],
                "provider_capabilities": config["provider_capabilities"],
                "combos": config["combos"],
                "failure_flags": config["failure_flags"],
                "provider_catalog": config["provider_catalog"],
                "secret_status": provider_secret_status(self.workspace, env_keys),
            }
        )

    def handle_provider_lab_save_secret(self, body: dict[str, Any]) -> None:
        env_key = str(body.get("env_key") or "").strip()
        value = str(body.get("value") or "").strip()
        if not env_key:
            raise ValueError("env_key is required")
        if not value:
            raise ValueError("secret value is required")
        config = load_guild_provider_config(self.workspace)
        env_keys = allowed_provider_env_keys(config["transports"])
        if env_key not in env_keys:
            raise ValueError(f"env_key is not allowed for provider lab: {env_key}")
        write_provider_secret(self.workspace, env_key, value)
        self.send_json(
            {
                "ok": True,
                "env_key": env_key,
                "secret_status": provider_secret_status(self.workspace, env_keys),
                "path": "_runtime/provider-secrets.local.ps1",
            }
        )

    def handle_provider_lab_list_models(self, body: dict[str, Any]) -> None:
        transport_name = str(body.get("transport") or "").strip()
        if not transport_name:
            raise ValueError("transport is required")
        config = load_guild_provider_config(self.workspace)
        transports = config["transports"]
        transport = transports.get(transport_name)
        if not transport:
            raise ValueError(f"unknown transport: {transport_name}")
        models = list_static_cartridge_models(config["cartridges"], transport_name)
        dynamic = list_provider_models(self.workspace, transport_name, transport)
        if dynamic.get("ok"):
            seen = {str(model.get("id")) for model in models}
            for model in dynamic.get("models") or []:
                model_id = str(model.get("id") or "").strip()
                if model_id and model_id not in seen:
                    models.append(model)
                    seen.add(model_id)
        self.send_json(
            {
                "ok": True,
                "transport": transport_name,
                "source": dynamic.get("source") if isinstance(dynamic, dict) else None,
                "models": models,
                "dynamic": dynamic,
            }
        )

    def handle_provider_lab_test(self, body: dict[str, Any]) -> None:
        cartridge = str(body.get("cartridge") or "").strip()
        model = str(body.get("model") or "").strip()
        capability = str(body.get("capability") or "deterministic-smoke").strip()
        profile = str(body.get("profile") or "builder").strip()
        title = str(body.get("title") or "provider-lab-smoke").strip()
        message = str(body.get("message") or "").strip()
        expect_terms = body.get("expect_terms") or []
        forbidden_terms = body.get("forbidden_terms") or []
        if not cartridge:
            raise ValueError("cartridge is required")
        if isinstance(expect_terms, str):
            expect_terms = [expect_terms]
        if isinstance(forbidden_terms, str):
            forbidden_terms = [forbidden_terms]
        if not message:
            message = (
                "Return only compact artifact JSON with ok=true, summary, files_changed, "
                "commands_run, test_result, known_risks, and blocked_reason. "
                "The summary must mention provider-lab-smoke and the selected capability."
            )
            expect_terms = [*expect_terms, "provider-lab-smoke", capability]
        args = [
            resolve_powershell_exe(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.workspace / "scripts" / "invoke-guild-provider-adapter.ps1"),
            "-Adapter",
            "auto-ammo",
            "-Profile",
            profile,
            "-Title",
            title,
            "-Provider",
            cartridge,
            "-Capability",
            capability,
            "-Message",
            message,
            "-Json",
        ]
        if model:
            args.extend(["-Model", model])
        expected = [str(term).strip() for term in expect_terms if str(term).strip()]
        forbidden = [str(term).strip() for term in forbidden_terms if str(term).strip()]
        if expected:
            args.extend(["-ExpectTerm", ",".join(expected)])
        if forbidden:
            args.extend(["-ForbiddenTerm", ",".join(forbidden)])
        completed = self.run_cmd(args, timeout=180)
        payload = parse_json_or_text(completed.stdout)
        payload_ok = bool(completed.returncode == 0)
        if isinstance(payload, dict):
            validation = payload.get("artifact_validation") or {}
            if validation and not validation.get("valid", False):
                payload_ok = False
        self.send_json(
            {
                "ok": payload_ok,
                "returncode": completed.returncode,
                "cartridge": cartridge,
                "capability": capability,
                "title": title,
                "result": payload,
                "stderr": completed.stderr,
            },
            status=200 if payload_ok else 502,
        )

    def handle_provider_lab_quick_add(self, body: dict[str, Any]) -> None:
        result = quick_add_provider(self.workspace, body)
        self.send_json(result, status=200 if result["ok"] else 400)

    def handle_provider_lab_save_combo(self, body: dict[str, Any]) -> None:
        result = save_provider_combo(self.workspace, body)
        self.send_json(result, status=200 if result["ok"] else 400)


def slugify(value: str) -> str:
    text = "".join(char.lower() if char.isalnum() else "-" for char in value)
    parts = [part for part in text.split("-") if part]
    return "-".join(parts[:8]) or "manual-quest"


def load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_config_id(value: str, fallback: str) -> str:
    raw = value.strip().lower()
    chars = [char if char.isalnum() else "-" for char in raw]
    result = "-".join(part for part in "".join(chars).split("-") if part)
    return result or fallback


def clean_env_key(value: str) -> str:
    raw = value.strip().upper()
    chars = [char if char.isalnum() else "_" for char in raw]
    result = "_".join(part for part in "".join(chars).split("_") if part)
    if result and not result.endswith("_API_KEY") and "KEY" not in result:
        result = f"{result}_API_KEY"
    return result


def normalize_chat_completions_url(value: str) -> tuple[str, list[str]]:
    repairs: list[str] = []
    url = value.strip()
    if not url:
        return "", repairs
    if url.rstrip("/").endswith("/v1"):
        url = url.rstrip("/") + "/chat/completions"
        repairs.append("expanded_base_v1_to_chat_completions_url")
    return url, repairs


def provider_catalog_default_base_url(workspace: Path, provider_id_or_label: str) -> str:
    known_chat_urls = {
        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        "openai": "https://api.openai.com/v1/chat/completions",
        "groq": "https://api.groq.com/openai/v1/chat/completions",
        "deepseek": "https://api.deepseek.com/v1/chat/completions",
        "mistral": "https://api.mistral.ai/v1/chat/completions",
        "xai": "https://api.x.ai/v1/chat/completions",
        "together": "https://api.together.xyz/v1/chat/completions",
        "fireworks": "https://api.fireworks.ai/inference/v1/chat/completions",
        "cerebras": "https://api.cerebras.ai/v1/chat/completions",
        "nebius": "https://api.studio.nebius.com/v1/chat/completions",
        "hyperbolic": "https://api.hyperbolic.xyz/v1/chat/completions",
        "siliconflow": "https://api.siliconflow.cn/v1/chat/completions",
        "vercel-ai-gateway": "https://ai-gateway.vercel.sh/v1/chat/completions",
    }
    catalog = load_json_file(
        workspace / "config" / "guild" / "provider-catalog.9router.json",
        {"providers": {}, "groups": {}},
    )
    providers = catalog.get("providers") or {}
    needle = clean_config_id(provider_id_or_label, "").replace("-", "")
    if needle in known_chat_urls:
      return known_chat_urls[needle]
    for provider in providers.values():
        if not isinstance(provider, dict):
            continue
        provider_id = clean_config_id(str(provider.get("id") or ""), "").replace("-", "")
        provider_name = clean_config_id(str(provider.get("name") or ""), "").replace("-", "")
        if needle and needle not in {provider_id, provider_name} and needle not in provider_id and needle not in provider_name:
            continue
        base_urls = provider.get("base_urls") or {}
        for key in ("llm", "chat", "search", "fetch", "embedding", "image", "tts", "stt"):
            value = str(base_urls.get(key) or "").strip()
            if value:
                return value
        for key in ("api_key_url", "website"):
            value = str(provider.get(key) or "").strip()
            if value:
                return value
    return ""


def quick_add_provider(workspace: Path, body: dict[str, Any]) -> dict[str, Any]:
    provider_label = str(body.get("label") or body.get("provider") or "").strip()
    provider_catalog_id = str(body.get("provider_id") or "").strip()
    model = str(body.get("model") or "").strip()
    base_url = str(body.get("base_url") or body.get("chat_completions_url") or "").strip()
    env_key = clean_env_key(str(body.get("env_key") or ""))
    secret_value = str(body.get("secret") or "").strip()
    capability = str(body.get("capability") or "code-edit-worker").strip()
    add_to_ladder = bool(body.get("add_to_ladder", True))

    errors: list[str] = []
    repairs: list[str] = []
    if not provider_label:
        errors.append("provider label is required")
    if not base_url and provider_catalog_id:
        base_url = provider_catalog_default_base_url(workspace, provider_catalog_id)
    if not base_url:
        errors.append("base URL is required")
    if not env_key:
        errors.append("env key is required")

    chat_url, url_repairs = normalize_chat_completions_url(base_url)
    repairs.extend(url_repairs)
    provider_id = clean_config_id(provider_label, "custom-provider")
    transport_id = clean_config_id(str(body.get("transport") or f"{provider_id}-http"), f"{provider_id}-http")
    cartridge_id = clean_config_id(str(body.get("cartridge") or f"{provider_id}-{model}"), provider_id)

    root = workspace / "config" / "guild"
    transports_path = root / "provider-transports.json"
    cartridges_path = root / "model-cartridges.json"
    capabilities_path = root / "capability-adapters.json"
    transports_doc = load_json_file(transports_path, {"schema_version": "guild_provider_transports_v0", "transports": {}})
    cartridges_doc = load_json_file(cartridges_path, {"schema_version": "guild_model_cartridges_v0", "cartridges": {}})
    capabilities_doc = load_json_file(capabilities_path, {"schema_version": "guild_capability_adapters_v0", "capabilities": {}})
    capabilities = capabilities_doc.get("capabilities") or {}
    if capability not in capabilities:
        errors.append(f"unknown capability: {capability}")

    if errors:
        return {
            "ok": False,
            "errors": errors,
            "repairs": repairs,
        }

    transports = transports_doc.setdefault("transports", {})
    cartridges = cartridges_doc.setdefault("cartridges", {})
    transports[transport_id] = {
        "kind": "openai_compatible_http",
        "backend_adapter": "openai-compatible",
        "requires_key": True,
        "env_keys": [env_key],
        "chat_completions_url": chat_url,
        "default_model": model,
        "label": provider_label,
        "notes": "Added from Provider Lab quick add. Secret value is stored only in ignored local provider secrets.",
    }
    cartridges[cartridge_id] = {
        "transport": transport_id,
        "model": model,
        "cost_tier": str(body.get("cost_tier") or "unknown"),
        "latency": str(body.get("latency") or "unknown"),
        "structured_output_reliability": str(body.get("reliability") or "unknown"),
        "notes": f"Quick-added cartridge for {provider_label}.",
    }

    ladder_updated = False
    if add_to_ladder:
        ladder = capabilities[capability].setdefault("ammo_ladder", [])
        if cartridge_id not in ladder:
            ladder.append(cartridge_id)
            ladder_updated = True

    save_json_file(transports_path, transports_doc)
    save_json_file(cartridges_path, cartridges_doc)
    save_json_file(capabilities_path, capabilities_doc)
    if secret_value:
        write_provider_secret(workspace, env_key, secret_value)

    env_keys = allowed_provider_env_keys(transports)
    return {
        "ok": True,
        "provider": provider_label,
        "transport": transport_id,
        "cartridge": cartridge_id,
        "capability": capability,
        "env_key": env_key,
        "secret_saved": bool(secret_value),
        "ladder_updated": ladder_updated,
        "repairs": repairs,
        "config": {
            "transports": transports,
            "cartridges": cartridges,
            "capabilities": capabilities,
            "secret_status": provider_secret_status(workspace, env_keys),
        },
    }


def save_provider_combo(workspace: Path, body: dict[str, Any]) -> dict[str, Any]:
    combo_name = clean_config_id(str(body.get("name") or ""), "combo")
    label = str(body.get("label") or combo_name).strip()
    capability = str(body.get("capability") or "code-edit-worker").strip()
    kind = str(body.get("kind") or "llm").strip()
    notes = str(body.get("notes") or "").strip()
    raw_items = body.get("items") or []
    if isinstance(raw_items, str):
        raw_items = [item.strip() for item in raw_items.split(",")]

    root = workspace / "config" / "guild"
    combos_path = root / "provider-combos.json"
    cartridges_doc = load_json_file(root / "model-cartridges.json", {"cartridges": {}})
    capabilities_doc = load_json_file(root / "capability-adapters.json", {"capabilities": {}})
    combos_doc = load_json_file(
        combos_path,
        {"schema_version": "guild_provider_combos_v0", "combos": {}},
    )
    cartridges = cartridges_doc.get("cartridges") or {}
    capabilities = capabilities_doc.get("capabilities") or {}
    errors: list[str] = []
    if not combo_name:
        errors.append("combo name is required")
    if capability not in capabilities:
        errors.append(f"unknown capability: {capability}")
    items = []
    for value in raw_items:
        cartridge = str(value or "").strip()
        if not cartridge:
            continue
        if cartridge not in cartridges:
            errors.append(f"unknown cartridge: {cartridge}")
            continue
        items.append(
            {
                "cartridge": cartridge,
                "on_flags": ["provider_service_unavailable", "provider_rate_limited", "provider_timeout"],
            }
        )
    if not items:
        errors.append("at least one cartridge is required")
    if errors:
        return {"ok": False, "errors": errors}

    combos = combos_doc.setdefault("combos", {})
    combos[combo_name] = {
        "kind": kind,
        "capability": capability,
        "label": label,
        "notes": notes or "Added from Provider Lab combo editor.",
        "items": items,
    }
    save_json_file(combos_path, combos_doc)
    return {
        "ok": True,
        "combo": combo_name,
        "combos": combos,
    }


def load_guild_runtime_config(workspace: Path) -> dict[str, Any]:
    default = {
        "schema_version": "guild_runtime_v1",
        "module_tracks": [
            {
                "id": "A",
                "index": 1,
                "skill": "requirements",
                "output_file": "build-1.md",
                "output_artifact": "implementation_result_1",
                "instruction": "Extract requirements and module contract.",
                "required_rank": "C",
            },
            {
                "id": "B",
                "index": 2,
                "skill": "risk-analysis",
                "output_file": "build-2.md",
                "output_artifact": "implementation_result_2",
                "instruction": "Identify risks, mismatches, and integration concerns.",
                "required_rank": "C",
            },
            {
                "id": "C",
                "index": 3,
                "skill": "verification",
                "output_file": "build-3.md",
                "output_artifact": "implementation_result_3",
                "instruction": "Create the verification checklist and acceptance evidence plan.",
                "required_rank": "C",
            },
        ],
        "scheduler": {
            "exclude_profiles": ["hermes-codex", "tester", "reviewer"],
            "preferred_adapters": {
                "worker-a": "gemini",
                "worker-b": "opencode",
                "worker-c": "openrouter",
                "reviewer": "groq",
            },
            "fallback_adapter_ladder": ["gemini", "opencode", "openrouter", "groq"],
        },
        "review": {
            "required_rank": "B",
            "required_skill": "integration_review",
            "max_fix_rounds": 3,
        },
        "final_assembly": {
            "review_file": "review.md",
            "summary_file": "final-summary.md",
            "artifact_file": "final-artifact.json",
        },
    }
    return load_json_file(workspace / "config" / "guild" / "guild-runtime.json", default)


def load_planner_skill_config(workspace: Path) -> dict[str, Any]:
    default = {
        "schema_version": "guild_planner_skills_v0",
        "default_template": "standard-build",
        "max_execution_tasks": 4,
        "templates": {},
        "rules": [],
    }
    return load_json_file(workspace / "config" / "guild" / "planner-skills.json", default)


def select_planner_template(config: dict[str, Any], title: str, request: str) -> tuple[str, dict[str, Any]]:
    templates = config.get("templates") or {}
    default_name = str(config.get("default_template") or "standard-build")
    text = f"{title}\n{request}".lower()
    best_name = default_name
    best_score = -1
    for name, template in templates.items():
        keywords = [str(item).lower() for item in template.get("match_keywords") or []]
        score = sum(1 for keyword in keywords if keyword and keyword in text)
        if score > best_score:
            best_name = str(name)
            best_score = score
    template = dict(templates.get(best_name) or templates.get(default_name) or {})
    return best_name, template


def build_skill_pack_planner(
    workspace: Path,
    *,
    title: str,
    request: str,
    runtime: dict[str, Any],
    fallback_reason: str,
) -> dict[str, Any]:
    config = load_planner_skill_config(workspace)
    template_name, template = select_planner_template(config, title, request)
    tracks = [dict(track) for track in template.get("tracks") or []]
    if not tracks:
        return build_runtime_fallback_planner(title=title, request=request, runtime=runtime, error=fallback_reason)
    planner = {
        "ok": True,
        "title": title,
        "request": request,
        "summary": f"Selected {template_name} planner template for a bounded Guild task split.",
        "template": template_name,
        "tracks": tracks,
        "review_instruction": str((template.get("review") or {}).get("instruction") or "Review upstream artifacts and write review.md plus final-summary.md."),
        "risks": [],
        "_fallback_reason": fallback_reason,
    }
    return validate_dynamic_planner(planner, workspace, runtime)


def runtime_module_tracks(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = []
    for index, raw in enumerate(runtime.get("module_tracks") or [], start=1):
        track = dict(raw)
        track["index"] = int(track.get("index") or index)
        track["id"] = str(track.get("id") or chr(ord("A") + index - 1))
        track["skill"] = str(track.get("skill") or "general")
        track["output_file"] = str(track.get("output_file") or f"build-{track['index']}.md")
        track["output_artifact"] = str(track.get("output_artifact") or f"implementation_result_{track['index']}")
        track["instruction"] = str(track.get("instruction") or "Complete this module.")
        track["required_rank"] = str(track.get("required_rank") or "C")
        tracks.append(track)
    return tracks


def normalize_planner_track(raw: dict[str, Any], index: int) -> dict[str, Any]:
    track = dict(raw)
    allowed_task_types = {"contract", "execution", "join_review", "fix", "final_review"}
    task_type = str(track.get("task_type") or "execution")
    if task_type not in allowed_task_types:
        track["planner_task_type"] = task_type
        task_type = "execution"
    track["index"] = int(track.get("index") or index)
    track["id"] = str(track.get("id") or chr(ord("A") + index - 1))
    track["title"] = str(track.get("title") or f"Track {track['id']}")
    track["task_type"] = task_type
    track["required_rank"] = str(track.get("required_rank") or "C")
    track["required_skill"] = str(track.get("required_skill") or track.get("skill") or "implementation")
    track["owner_area"] = str(track.get("owner_area") or "implementation")
    track["output_file"] = str(track.get("output_file") or f"build-{track['index']}.md")
    track["output_artifact"] = str(track.get("output_artifact") or f"implementation_result_{track['index']}")
    track["instruction"] = str(track.get("instruction") or "Complete this bounded Guild task.")
    return track


def validate_dynamic_planner(planner: dict[str, Any], workspace: Path, runtime: dict[str, Any]) -> dict[str, Any]:
    tracks = [normalize_planner_track(track, index) for index, track in enumerate(planner.get("tracks") or [], start=1)]
    if not tracks:
        raise RuntimeError("Hermes planner returned no tracks.")
    max_tasks = int(load_planner_skill_config(workspace).get("max_execution_tasks") or 4)
    execution_count = sum(1 for track in tracks if track["task_type"] not in {"contract"})
    if execution_count > max_tasks:
        raise RuntimeError(f"Hermes planner produced too many execution tasks: {execution_count}>{max_tasks}")
    seen_files: set[str] = set()
    for track in tracks:
        output_file = str(track["output_file"])
        if "/" in output_file or "\\" in output_file or output_file.startswith("."):
            raise RuntimeError(f"Planner output_file must be a simple quest-workspace filename: {output_file}")
        if output_file in seen_files:
            raise RuntimeError(f"Planner output_file is duplicated: {output_file}")
        seen_files.add(output_file)
    result = dict(planner)
    result["ok"] = True
    result["tracks"] = tracks
    result["review_instruction"] = str(result.get("review_instruction") or "Review upstream artifacts and write review.md plus final-summary.md.")
    return result


def load_agent_profiles(workspace: Path) -> dict[str, Any]:
    data = load_json_file(workspace / "config" / "guild" / "agent-profiles.json", {"profiles": {}})
    return data.get("profiles") or {}


def rank_value(rank: str) -> int:
    return {"D": 1, "C": 2, "B": 3, "A": 4, "S": 5}.get(str(rank), 0)


def profile_can_run_track(profile: dict[str, Any], track: dict[str, Any]) -> bool:
    skills = [str(skill) for skill in profile.get("skills") or []]
    return rank_value(str(profile.get("rank") or "D")) >= rank_value(str(track.get("required_rank") or "C")) and str(track["skill"]) in skills


def profile_can_run_review(profile: dict[str, Any], review: dict[str, Any]) -> bool:
    skills = [str(skill) for skill in profile.get("skills") or []]
    return (
        rank_value(str(profile.get("rank") or "D")) >= rank_value(str(review.get("required_rank") or "B"))
        and str(review.get("required_skill") or "integration_review") in skills
    )


def schedule_worker_profiles(workspace: Path, runtime: dict[str, Any]) -> list[str]:
    profiles = load_agent_profiles(workspace)
    scheduler = runtime.get("scheduler") or {}
    excluded = {str(item) for item in scheduler.get("exclude_profiles") or []}
    selected: list[str] = []
    for track in runtime_module_tracks(runtime):
        candidates = [
            (name, profile)
            for name, profile in profiles.items()
            if name not in excluded and profile_can_run_track(profile, track)
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda item: (rank_value(str(item[1].get("rank") or "D")), item[0]))
        name = candidates[0][0]
        if name not in selected:
            selected.append(name)
    return selected


def schedule_quest_wake_profiles(workspace: Path, runtime: dict[str, Any]) -> list[str]:
    profiles = load_agent_profiles(workspace)
    selected = schedule_worker_profiles(workspace, runtime)
    review = runtime.get("review") or {}
    review_candidates = [
        (name, profile)
        for name, profile in profiles.items()
        if name not in selected and profile_can_run_review(profile, review)
    ]
    review_candidates.sort(key=lambda item: (rank_value(str(item[1].get("rank") or "D")), item[0]))
    if review_candidates:
        selected.append(review_candidates[0][0])
    return selected


def module_track_for_task(task: dict[str, Any], tracks: list[dict[str, Any]]) -> dict[str, Any] | None:
    task_id = str(task.get("task_id") or "")
    task_skill = str(task.get("required_skill") or "")
    output_artifact = str(task.get("output_artifact") or "")
    for track in tracks:
        index = int(track["index"])
        if task_id.endswith(f"-build-{index}") or task_skill == track["skill"] or output_artifact == track["output_artifact"]:
            return track
    return None


def fan_in_tasks_for_review(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fan_in_types = {"execution", "verification", "analysis", "fix"}
    return [
        task
        for task in tasks
        if str(task.get("task_type") or "") in fan_in_types
        and str(task.get("generated_from") or "") == ""
    ]


def planner_tracks_from_tasks(tasks: list[dict[str, Any]], runtime: dict[str, Any]) -> list[dict[str, Any]]:
    runtime_tracks = runtime_module_tracks(runtime)
    tracks: list[dict[str, Any]] = []
    for index, task in enumerate(sorted(tasks, key=lambda item: int(item.get("sequence_no") or 0)), start=1):
        output_file = extract_assigned_output_file(str(task.get("request") or ""))
        if output_file:
            tracks.append(
                {
                    "id": str(index),
                    "index": index,
                    "skill": str(task.get("required_skill") or "general"),
                    "output_file": output_file,
                    "output_artifact": str(task.get("output_artifact") or f"task_result_{index}"),
                    "instruction": str(task.get("title") or "Complete this task."),
                    "required_rank": str(task.get("required_rank") or "C"),
                }
            )
            continue
        matched = module_track_for_task(task, runtime_tracks)
        if matched:
            tracks.append(matched)
            continue
        tracks.append(
            {
                "id": str(index),
                "index": index,
                "skill": str(task.get("required_skill") or "general"),
                "output_file": output_file,
                "output_artifact": str(task.get("output_artifact") or f"task_result_{index}"),
                "instruction": str(task.get("title") or "Complete this task."),
                "required_rank": str(task.get("required_rank") or "C"),
            }
        )
    return tracks


def extract_assigned_output_file(request: str) -> str | None:
    marker = "Assigned output file:"
    for line in request.splitlines():
        if marker in line:
            value = line.split(marker, 1)[1].strip()
            if value and "/" not in value and "\\" not in value:
                return value
    return None


def validate_final_outputs(
    workspace: Path,
    quest_workspace: Path,
    tracks: list[dict[str, Any]],
    final_paths: list[Path],
) -> list[dict[str, Any]]:
    paths = [quest_workspace / str(track["output_file"]) for track in tracks]
    paths.extend(final_paths)
    validations = []
    for path in paths:
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        validations.append(
            {
                "path": str(path.relative_to(workspace)),
                "ok": exists and size > 0,
                "exists": exists,
                "bytes": size,
            }
        )
    return validations


def task_failed_only_by_grounding_gate(workspace: Path, task: dict[str, Any]) -> bool:
    task_id = str(task.get("task_id") or "")
    if not task_id:
        return False
    payload_dir = workspace / "_runtime" / "guild-worker-agent"
    if not payload_dir.is_dir():
        return False
    payloads = sorted(payload_dir.glob(f"{task_id}-*-payload.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    payloads.extend(sorted(payload_dir.glob(f"{task_id}-payload.json"), key=lambda item: item.stat().st_mtime, reverse=True))
    for payload_path in payloads:
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if payload.get("blocked_reason") != "ungrounded_artifact_output":
            continue
        adapter_result = payload.get("adapter_result") or {}
        artifact_validation = payload.get("adapter_output_validation") or {}
        scope_validation = payload.get("file_scope_validation") or {}
        if adapter_result.get("ok") is True and artifact_validation.get("valid") is True and scope_validation.get("valid") is True:
            return True
    return False


def load_guild_provider_config(workspace: Path) -> dict[str, Any]:
    root = workspace / "config" / "guild"
    return {
        "transports": load_json_file(root / "provider-transports.json", {"transports": {}}).get("transports", {}),
        "cartridges": load_json_file(root / "model-cartridges.json", {"cartridges": {}}).get("cartridges", {}),
        "capabilities": load_json_file(root / "capability-adapters.json", {"capabilities": {}}).get("capabilities", {}),
        "provider_capabilities": load_json_file(root / "provider-capabilities.json", {"capabilities": {}}).get("capabilities", {}),
        "combos": load_json_file(root / "provider-combos.json", {"combos": {}}).get("combos", {}),
        "failure_flags": load_json_file(root / "failure-flags.json", {"flags": {}}).get("flags", {}),
        "provider_catalog": load_json_file(root / "provider-catalog.9router.json", {"providers": {}, "groups": {}}),
    }


def allowed_provider_env_keys(transports: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for transport in transports.values():
        for key in transport.get("env_keys") or []:
            if isinstance(key, str) and key.strip():
                keys.add(key.strip())
    return keys


def provider_secret_path(workspace: Path) -> Path:
    return workspace / "_runtime" / "provider-secrets.local.ps1"


def read_local_secret_names(workspace: Path) -> set[str]:
    path = provider_secret_path(workspace)
    if not path.is_file():
        return set()
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped.startswith("$env:") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].replace("$env:", "", 1).strip()
        if name:
            names.add(name)
    return names


def provider_secret_status(workspace: Path, env_keys: set[str]) -> dict[str, Any]:
    local_names = read_local_secret_names(workspace)
    return {
        key: {
            "has_key": bool(os.environ.get(key)) or key in local_names,
            "source": "env" if os.environ.get(key) else ("local" if key in local_names else "missing"),
        }
        for key in sorted(env_keys)
    }


def powershell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_provider_secret(workspace: Path, env_key: str, value: str) -> None:
    path = provider_secret_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    replaced = False
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith(f"$env:{env_key}") and "=" in stripped:
                lines.append(f"$env:{env_key} = {powershell_single_quote(value)}")
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        if lines:
            lines.append("")
        lines.append(f"$env:{env_key} = {powershell_single_quote(value)}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_provider_secret_value(workspace: Path, env_key: str) -> str | None:
    if os.environ.get(env_key):
        return os.environ[env_key]
    path = provider_secret_path(workspace)
    if not path.is_file():
        return None
    prefix = f"$env:{env_key}"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix) or "=" not in stripped:
            continue
        raw = stripped.split("=", 1)[1].strip()
        if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
            return raw[1:-1].replace("''", "'")
    return None


def list_static_cartridge_models(cartridges: dict[str, Any], transport_name: str) -> list[dict[str, Any]]:
    models = []
    for name, cartridge in cartridges.items():
        if str(cartridge.get("transport") or "") != transport_name:
            continue
        models.append(
            {
                "id": cartridge.get("model") or name,
                "cartridge": name,
                "source": "cartridge",
                "label": name,
            }
        )
    return models


def derive_models_endpoint(base_url: str) -> str:
    url = str(base_url or "").strip()
    if not url:
        return ""
    url = url.rstrip("/")
    if url.endswith("/chat/completions") or url.endswith("/completions"):
        url = url.rsplit("/", 2)[0]
    if url.endswith("/models"):
        return url
    return f"{url}/models"


def build_models_request_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "HermesGuildCore/1.0",
    }


def load_provider_models_payload(response: Any) -> dict[str, Any]:
    body = response.read()
    text = body.decode("utf-8", errors="replace")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("models response was not an object")
    return data


def list_provider_models(workspace: Path, transport_name: str, transport: dict[str, Any]) -> dict[str, Any]:
    if transport_name == "local-dry-run":
        return {"ok": True, "source": "deterministic", "models": [{"id": "local-dry-run", "source": "deterministic"}]}
    transport_kind = str(transport.get("kind") or "").strip()
    if transport_kind in {"deterministic", "cli"} and transport_name != "opencode-cli":
        return {"ok": False, "reason": "cli_transport_no_model_endpoint"}
    if transport_name == "opencode-cli":
        completed = subprocess.run(
            ["opencode", "models"],
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if completed.returncode != 0:
            return {"ok": False, "reason": "opencode_models_failed", "stderr": completed.stderr}
        models = []
        for line in completed.stdout.splitlines():
            text = line.strip()
            if text and "/" in text and " " not in text:
                models.append({"id": text, "source": "opencode"})
        return {"ok": True, "source": "opencode", "models": models, "raw_count": len(completed.stdout.splitlines())}

    env_keys = [str(key) for key in transport.get("env_keys") or []]
    api_key = None
    for key in env_keys:
        api_key = read_provider_secret_value(workspace, key)
        if api_key:
            break
    if not api_key:
        return {"ok": False, "reason": "provider_missing", "missing_env_keys": env_keys}

    endpoint_candidates = [
        str(transport.get("models_url") or "").strip(),
        str(transport.get("chat_completions_url") or "").strip(),
        str(transport.get("base_url") or "").strip(),
    ]
    endpoint = ""
    for candidate in endpoint_candidates:
        if candidate:
            endpoint = derive_models_endpoint(candidate)
            if endpoint:
                break

    backend_adapter = str(transport.get("backend_adapter") or "").strip()
    if not endpoint:
        fallback_map = {
            "openrouter": "https://openrouter.ai/api/v1/models",
            "groq": "https://api.groq.com/openai/v1/models",
            "openai-compatible": "https://api.openai.com/v1/models",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
            "openai": "https://api.openai.com/v1/models",
        }
        endpoint = fallback_map.get(backend_adapter, "")

    try:
        if transport_name == "gemini-api" or backend_adapter == "gemini":
            url = endpoint or "https://generativelanguage.googleapis.com/v1beta/models"
            if "googleapis.com" in url and "key=" not in url:
                url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode({"key": api_key})
                request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "HermesGuildCore/1.0"})
            else:
                request = urllib.request.Request(url, headers=build_models_request_headers(api_key))
            with urllib.request.urlopen(request, timeout=20) as response:
                data = load_provider_models_payload(response)
            raw_models = data.get("models", []) if isinstance(data.get("models"), list) else data.get("data", [])
            return {
                "ok": True,
                "source": "provider",
                "models": [
                    {
                        "id": str(item.get("name") or item.get("id") or "").replace("models/", ""),
                        "source": "provider",
                    }
                    for item in raw_models
                    if isinstance(item, dict) and (item.get("name") or item.get("id"))
                ],
            }
        if not endpoint:
            return {"ok": False, "reason": "models_endpoint_unavailable"}
        request = urllib.request.Request(endpoint, headers=build_models_request_headers(api_key))
        with urllib.request.urlopen(request, timeout=20) as response:
            data = load_provider_models_payload(response)
        raw_models = data.get("data", [])
        if not isinstance(raw_models, list):
            raw_models = []
        return {
            "ok": True,
            "source": "provider",
            "models": [
                {"id": str(item.get("id") or "").strip(), "source": "provider"}
                for item in raw_models
                if isinstance(item, dict) and str(item.get("id") or "").strip()
            ],
        }
    except Exception as exc:
        return {"ok": False, "reason": "provider_failed", "error": str(exc), "endpoint": endpoint}
    return {"ok": False, "reason": "list_models_not_supported"}


def parse_json_or_text(text: str) -> Any:
    value = (text or "").strip()
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value[-4000:]}


def tail_text(value: str | None, max_chars: int = 1200) -> str:
    text = str(value or "")
    return text[-max_chars:] if len(text) > max_chars else text


def append_event_log(workspace: Path, event: str, details: dict[str, Any]) -> None:
    log_dir = workspace / "_runtime" / "dashboard"
    log_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": event,
        "details": sanitize_log_value(details),
    }
    with (log_dir / "guild-events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_json_atomic(path: Path, data: Any, *, attempts: int = 20) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    temp_path.write_text(payload, encoding="utf-8")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            os.replace(temp_path, path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(min(0.15 * attempt, 2.0))
    try:
        temp_path.unlink(missing_ok=True)
    finally:
        if last_error:
            raise last_error


def cancel_quest_tasks(db_path: Path, quest_chain_id: str) -> list[str]:
    cancellable = {"open", "claimed", "running", "blocked", "review"}
    cancelled: list[str] = []
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            select task_id, status, payload_json
            from guild_tasks
            where quest_chain_id = ?
            """,
            (quest_chain_id,),
        ).fetchall()
        for row in rows:
            if str(row["status"] or "") not in cancellable:
                continue
            payload = json.loads(row["payload_json"])
            payload["status"] = "cancelled"
            payload["blocked_reason"] = None
            task_id = str(row["task_id"])
            con.execute(
                """
                update guild_tasks
                set status = 'cancelled',
                    assignee_id = null,
                    claimed_at = null,
                    lease_until = null,
                    heartbeat_at = null,
                    updated_at = datetime('now'),
                    payload_json = ?
                where task_id = ?
                """,
                (json.dumps(payload, ensure_ascii=False), task_id),
            )
            cancelled.append(task_id)
    return cancelled


def write_quest_stop_marker(workspace: Path, quest_chain_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "-", quest_chain_id)
    stop_dir = workspace / "_runtime" / "guild-worker-agent" / "quest-stops"
    stop_dir.mkdir(parents=True, exist_ok=True)
    stop_path = stop_dir / f"{safe_id}.stop"
    stop_path.write_text(
        json.dumps(
            {
                "quest_chain_id": quest_chain_id,
                "stopped_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return stop_path


def sanitize_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if any(marker in name.lower() for marker in ["secret", "token", "key", "password"]):
                clean[name] = "[redacted]"
            else:
                clean[name] = sanitize_log_value(item)
        return clean
    if isinstance(value, list):
        return [sanitize_log_value(item) for item in value[:20]]
    if isinstance(value, str):
        redacted = value
        if len(redacted) > 2000:
            redacted = redacted[-2000:]
        return redacted
    return value


def resolve_hermes_cli(workspace: Path) -> str:
    env_path = os.environ.get("HERMES_CLI")
    if env_path and Path(env_path).is_file():
        return str(Path(env_path))

    path_command = shutil.which("hermes")
    if path_command:
        return path_command

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "hermes" / "hermes-agent" / "venv" / "Scripts" / "hermes.exe"
        if candidate.is_file():
            return str(candidate)

    map_path = workspace / "HERMES_MAP.md"
    if map_path.is_file():
        for line in map_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "Hermes CLI:" not in line:
                continue
            candidate_text = line.split("Hermes CLI:", 1)[1].strip().strip("`")
            candidate = Path(candidate_text)
            if candidate.is_file():
                return str(candidate)

    raise FileNotFoundError("Hermes CLI not found. Set HERMES_CLI or check HERMES_MAP.md.")


def resolve_worker_adapters(adapter: str, profiles: list[Any], runtime: dict[str, Any] | None = None) -> list[str]:
    return [str(route["adapter"]) for route in resolve_worker_routes(adapter, profiles, runtime, Path.cwd())]


def capability_ammo_ladder(workspace: Path, capability_name: str) -> list[str]:
    config = load_json_file(workspace / "config" / "guild" / "capability-adapters.json", {"capabilities": {}})
    capability = (config.get("capabilities") or {}).get(capability_name) or {}
    return [str(item) for item in capability.get("ammo_ladder") or [] if str(item).strip()]


def rotated_item(items: list[str], index: int) -> str | None:
    if not items:
        return None
    return items[index % len(items)]


def resolve_worker_routes(
    adapter: str,
    profiles: list[Any],
    runtime: dict[str, Any] | None = None,
    workspace: Path | None = None,
) -> list[dict[str, Any]]:
    if adapter not in {"auto-rank", "rank-auto", "auto", "auto-ammo"}:
        return [
            {
                "profile": str(profile),
                "adapter": adapter,
                "provider": None,
                "model": None,
                "capability": None,
                "reason": "explicit_adapter",
            }
            for profile in profiles
        ]

    # auto-rank is a distribution policy; auto-ammo is the provider fallback loader.
    workspace = workspace or Path.cwd()
    scheduler = (runtime or {}).get("scheduler") or {}
    policy = str(scheduler.get("provider_policy") or "legacy_preferred")
    if policy == "legacy_preferred":
        preferred = scheduler.get("preferred_adapters") or scheduler.get("legacy_preferred_adapters") or {}
        build_ladder = [str(item) for item in scheduler.get("fallback_adapter_ladder") or ["opencode", "openrouter", "groq"]]
        build_index = 0
        result = []
        for profile in profiles:
            name = str(profile)
            if name in preferred:
                chosen = str(preferred[name])
                reason = "legacy_preferred_adapter"
            else:
                chosen = build_ladder[min(build_index, len(build_ladder) - 1)]
                build_index += 1
                reason = "legacy_fallback_adapter"
            result.append(
                {
                    "profile": name,
                    "adapter": chosen,
                    "provider": None,
                    "model": None,
                    "capability": None,
                    "reason": reason,
                }
            )
        return result

    auto_adapter = str(scheduler.get("auto_rank_adapter") or "auto-ammo")
    build_capability = str(scheduler.get("build_capability") or "code-edit-worker")
    review_capability = str(scheduler.get("review_capability") or "join-review-worker")
    build_ladder = capability_ammo_ladder(workspace, build_capability)
    review_ladder = capability_ammo_ladder(workspace, review_capability)
    agent_profiles = load_agent_profiles(workspace)
    review = (runtime or {}).get("review") or {}
    build_index = 0
    review_index = 0
    result: list[dict[str, Any]] = []
    for profile in profiles:
        name = str(profile)
        profile_config = agent_profiles.get(name) or {}
        is_review = profile_can_run_review(profile_config, review)
        if is_review:
            capability = review_capability
            provider = rotated_item(review_ladder, review_index)
            review_index += 1
            reason = "capability_pool_review"
        else:
            capability = build_capability
            provider = rotated_item(build_ladder, build_index)
            build_index += 1
            reason = "capability_pool_build"
        result.append(
            {
                "profile": name,
                "adapter": auto_adapter,
                "provider": provider,
                "model": None,
                "capability": capability,
                "reason": reason,
            }
        )
    return result


def join_allowed_files(*values: str) -> str:
    parts: list[str] = []
    for value in values:
        for part in str(value or "").split(","):
            cleaned = part.strip()
            if cleaned and cleaned not in parts:
                parts.append(cleaned)
    return ",".join(parts)


def create_quest_workspace(
    workspace: Path,
    quest_chain_id: str,
    title: str,
    request: str,
    planner: dict[str, Any] | None = None,
) -> Path:
    runtime = load_guild_runtime_config(workspace)
    final_config = runtime.get("final_assembly") or {}
    root = workspace / "guild-workspaces"
    quest_workspace = root / quest_chain_id
    quest_workspace.mkdir(parents=True, exist_ok=True)
    brief = quest_workspace / "task-brief.md"
    planner_summary = str((planner or {}).get("summary") or "").strip()
    brief.write_text(
        "\n".join(
            [
                f"# {title}",
                "",
                f"- quest_chain_id: `{quest_chain_id}`",
                "- owner: Hermes S-rank manager",
                "- rule: workers may write quest output files in this folder",
                "",
                "## Hermes Summary",
                "",
                planner_summary or "Manual router workspace.",
                "",
                "## Request",
                "",
                request,
                "",
                "## Expected Worker Files",
                "",
                *[f"- `{track['output_file']}`" for track in runtime_module_tracks(runtime)],
                f"- `{final_config.get('review_file') or 'review.md'}` from reviewer worker",
                f"- `{final_config.get('summary_file') or 'final-summary.md'}` from reviewer worker",
                f"- `{final_config.get('artifact_file') or 'final-artifact.json'}` durable final artifact from Hermes finalizer",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if planner is not None:
        (quest_workspace / "hermes-plan.json").write_text(
            json.dumps(planner, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return quest_workspace


def extract_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            candidate = "\n".join(lines[1:-1]).strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(candidate[start : end + 1])


def resolve_powershell_exe() -> str:
    for name in ("powershell", "pwsh"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    windir = os.environ.get("WINDIR")
    if windir:
        candidate = Path(windir) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("PowerShell executable is required for worker wake.")


def validate_hermes_planner(planner: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    expected_tracks = runtime_module_tracks(runtime)
    errors: list[str] = []

    if planner.get("ok") is not True:
        errors.append("planner_ok_must_be_true")

    for field in ("title", "request", "summary", "review_instruction"):
        if not str(planner.get(field) or "").strip():
            errors.append(f"missing_{field}")

    tracks = planner.get("tracks")
    if not isinstance(tracks, list):
        errors.append("tracks_must_be_array")
        tracks = []
    if len(tracks) != len(expected_tracks):
        errors.append(
            f"tracks_count_must_equal_config:{len(tracks)}!={len(expected_tracks)}"
        )

    for index, expected in enumerate(expected_tracks):
        if index >= len(tracks):
            break
        actual = tracks[index] if isinstance(tracks[index], dict) else {}
        expected_id = str(expected["id"])
        actual_id = str(actual.get("id") or "")
        if actual_id != expected_id:
            errors.append(f"track_{expected_id}_id_mismatch:{actual_id}")
        if not str(actual.get("title") or "").strip():
            errors.append(f"track_{expected_id}_missing_title")
        if not str(actual.get("instruction") or "").strip():
            errors.append(f"track_{expected_id}_missing_instruction")

    if errors:
        raise ValueError("invalid_hermes_planner_output: " + "; ".join(errors))

    return planner


def build_runtime_fallback_planner(title: str, request: str, runtime: dict[str, Any], error: str) -> dict[str, Any]:
    tracks = []
    for track in runtime_module_tracks(runtime):
        tracks.append(
            {
                "id": str(track["id"]),
                "title": f"Build track {track['id']}",
                "instruction": "\n".join(
                    [
                        str(track["instruction"]),
                        "",
                        "Use the user request as source material.",
                        f"Focus only on the {track['skill']} module.",
                    ]
                ),
            }
        )
    return {
        "ok": True,
        "title": title,
        "request": request,
        "summary": "Runtime-config planner fallback created a bounded worker plan because Hermes planner did not return usable JSON.",
        "tracks": tracks,
        "review_instruction": "Compare the module outputs, identify mismatches, then write review.md and final-summary.md inside the quest workspace.",
        "risks": [tail_text(error, 500)] if error else [],
        "_hermes_provider": "fallback",
        "_hermes_model": "runtime-config",
        "_fallback_reason": tail_text(error, 500),
    }


def flatten_worker_summaries(summaries: list[tuple[str, str]]) -> list[str]:
    lines: list[str] = ["## Worker Outputs", ""]
    for filename, content in summaries:
        excerpt = " ".join(content.split())
        if len(excerpt) > 420:
            excerpt = f"{excerpt[:420].rstrip()}..."
        lines.extend([f"### {filename}", "", excerpt or "(empty file)", ""])
    return lines


def build_manual_plan(
    quest_chain_id: str,
    title: str,
    request: str,
    allowed_files: str,
    quest_workspace: Path,
    runtime: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    prefix = quest_chain_id.replace("quest-", "", 1)
    workspace_rel = quest_workspace.as_posix()
    worker_tracks = runtime_module_tracks(runtime)
    review = runtime.get("review") or {}

    def worker_request(track: dict[str, Any]) -> str:
        return "\n".join(
            [
                request,
                "",
                f"Quest workspace: {workspace_rel}",
                f"Assigned module: track {track['id']} / {track['skill']}",
                str(track["instruction"]),
                f"Write your visible deliverable to {track['output_file']} inside the quest workspace.",
                "Return artifact JSON listing the file you wrote.",
            ]
        )
    base = {
        "quest_chain_id": quest_chain_id,
        "allowed_files": allowed_files,
    }
    tasks = [
        {
            **base,
            "task_id": f"{prefix}-spec",
            "task_type": "contract",
            "required_rank": "C",
            "required_skill": "planning",
            "owner_area": "product",
            "status": "done",
            "plan_review_status": "not_required",
            "sequence_no": 1,
            "depends_on": [],
            "output_artifact": "app_spec",
            "title": f"Spec: {title}",
            "request": request,
        },
        *[
            {
                **base,
                "task_id": f"{prefix}-build-{track['index']}",
                "task_type": "execution",
                "required_rank": str(track["required_rank"]),
                "required_skill": str(track["skill"]),
                "owner_area": "implementation",
                "status": "blocked",
                "plan_review_status": "approved",
                "sequence_no": int(track["index"]) + 1,
                "depends_on": [f"{prefix}-spec"],
                "output_artifact": str(track["output_artifact"]),
                "title": f"Build track {track['id']}: {title}",
                "request": worker_request(track),
            }
            for track in worker_tracks
        ],
        {
            **base,
            "task_id": f"{prefix}-review",
            "task_type": "join_review",
            "required_rank": str(review.get("required_rank") or "B"),
            "required_skill": str(review.get("required_skill") or "integration_review"),
            "owner_area": "review",
            "status": "blocked",
            "plan_review_status": "approved",
            "sequence_no": len(worker_tracks) + 2,
            "depends_on": [f"{prefix}-build-{track['index']}" for track in worker_tracks],
            "output_artifact": "integration_report",
            "title": f"Review: {title}",
            "request": "\n".join(
                [
                    request,
                    "",
                    f"Quest workspace: {workspace_rel}",
                    "Read configured module outputs: "
                    + ", ".join(str(track["output_file"]) for track in worker_tracks)
                    + ".",
                    "If modules mismatch, request bounded fix tasks for the responsible module.",
                    "If all modules align, write review.md and final-summary.md.",
                ]
            ),
        },
    ]
    return (
        tasks,
        [
            "Hermes Guild router received the prompt.",
            "Applied config-driven module router: "
            + " -> ".join(str(track["skill"]) for track in worker_tracks)
            + " -> review.",
            "Prepared skill-bound worker claims and join-review gate.",
        ],
        schedule_quest_wake_profiles(quest_workspace.parents[1], runtime),
    )


def build_hermes_plan(
    *,
    quest_chain_id: str,
    title: str,
    request: str,
    allowed_files: str,
    quest_workspace: Path,
    planner: dict[str, Any],
    runtime: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    tracks = list(planner.get("tracks") or [])
    module_tracks = runtime_module_tracks(runtime)
    if len(tracks) != len(module_tracks):
        raise RuntimeError(
            f"Hermes planner track count mismatch: got {len(tracks)}, expected {len(module_tracks)}"
        )
    review = runtime.get("review") or {}
    prefix = quest_chain_id.replace("quest-", "", 1)
    workspace_rel = quest_workspace.as_posix()
    base = {
        "quest_chain_id": quest_chain_id,
        "allowed_files": allowed_files,
    }

    def worker_request(index: int, track: dict[str, Any]) -> str:
        module = module_tracks[index - 1]
        return "\n".join(
            [
                str(track.get("instruction") or request),
                "",
                f"Quest workspace: {workspace_rel}",
                f"Assigned module: track {module['id']} / {module['skill']}",
                f"Write your visible deliverable to {module['output_file']} inside the quest workspace.",
                "Return artifact JSON listing the file you wrote.",
            ]
        )

    tasks = [
        {
            **base,
            "task_id": f"{prefix}-spec",
            "task_type": "contract",
            "required_rank": "C",
            "required_skill": "planning",
            "owner_area": "product",
            "status": "done",
            "plan_review_status": "not_required",
            "sequence_no": 1,
            "depends_on": [],
            "output_artifact": "app_spec",
            "title": f"Spec: {title}",
            "request": request,
        }
    ]
    for index, track in enumerate(tracks, start=1):
        tasks.append(
            {
                **base,
                "task_id": f"{prefix}-build-{module_tracks[index - 1]['index']}",
                "task_type": "execution",
                "required_rank": str(module_tracks[index - 1]["required_rank"]),
                "required_skill": str(module_tracks[index - 1]["skill"]),
                "owner_area": "implementation",
                "status": "blocked",
                "plan_review_status": "approved",
                "sequence_no": int(module_tracks[index - 1]["index"]) + 1,
                "depends_on": [f"{prefix}-spec"],
                "output_artifact": str(module_tracks[index - 1]["output_artifact"]),
                "title": f"{track.get('title') or f'Build track {index}'}: {title}",
                "request": worker_request(index, track),
            }
        )
    review_instruction = str(planner.get("review_instruction") or "Review all build artifacts and write review.md plus final-summary.md.")
    tasks.append(
        {
            **base,
            "task_id": f"{prefix}-review",
            "task_type": "join_review",
            "required_rank": str(review.get("required_rank") or "B"),
            "required_skill": str(review.get("required_skill") or "integration_review"),
            "owner_area": "review",
            "status": "blocked",
            "plan_review_status": "approved",
            "sequence_no": len(module_tracks) + 2,
            "depends_on": [f"{prefix}-build-{track['index']}" for track in module_tracks],
            "output_artifact": "integration_report",
            "title": f"Review: {title}",
            "request": "\n".join(
                [
                    review_instruction,
                    "",
                    f"Quest workspace: {workspace_rel}",
                    "Read upstream artifacts and workspace files.",
                    "Write review.md and final-summary.md inside the quest workspace.",
                    "Return artifact JSON listing the file(s) you wrote.",
                ]
            ),
        }
    )
    return (
        tasks,
        [
            "Hermes S-rank planner received the prompt.",
            f"Hermes provider/model: {planner.get('_hermes_provider')} / {planner.get('_hermes_model')}",
            str(planner.get("summary") or "Hermes produced a bounded worker plan."),
            "Posted Hermes-derived tasks to blackboard.",
        ],
        schedule_quest_wake_profiles(quest_workspace.parents[1], runtime),
    )


def build_dynamic_hermes_plan(
    *,
    quest_chain_id: str,
    title: str,
    request: str,
    allowed_files: str,
    quest_workspace: Path,
    planner: dict[str, Any],
    runtime: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    tracks = [normalize_planner_track(track, index) for index, track in enumerate(planner.get("tracks") or [], start=1)]
    if not tracks:
        raise RuntimeError("Hermes planner returned no tracks.")
    review = runtime.get("review") or {}
    prefix = quest_chain_id.replace("quest-", "", 1)
    workspace_rel = quest_workspace.as_posix()
    base = {
        "quest_chain_id": quest_chain_id,
        "allowed_files": allowed_files,
    }
    tasks: list[dict[str, Any]] = []
    prior_ids: list[str] = []

    for index, track in enumerate(tracks, start=1):
        is_contract = str(track["task_type"]) == "contract"
        task_id = f"{prefix}-spec" if is_contract and not prior_ids else f"{prefix}-task-{index}"
        depends_on = [] if is_contract or not prior_ids else [prior_ids[0]]
        task = {
            **base,
            "task_id": task_id,
            "task_type": str(track["task_type"]),
            "required_rank": str(track["required_rank"]),
            "required_skill": str(track["required_skill"]),
            "owner_area": str(track["owner_area"]),
            "status": "done" if is_contract else "blocked",
            "plan_review_status": "not_required" if is_contract else "approved",
            "sequence_no": index,
            "depends_on": depends_on,
            "output_artifact": str(track["output_artifact"]),
            "title": f"{track['title']}: {title}",
            "request": "\n".join(
                [
                    str(track["instruction"]),
                    "",
                    f"Quest workspace: {workspace_rel}",
                    f"Assigned planner template: {planner.get('template') or 'custom'}",
                    f"Assigned output file: {track['output_file']}",
                    "Write your visible deliverable inside the quest workspace.",
                    "Return artifact JSON listing the file you wrote.",
                    "",
                    "Original user request:",
                    request,
                ]
            ),
        }
        tasks.append(task)
        prior_ids.append(task_id)

    executable_ids = [task["task_id"] for task in tasks if str(task["task_type"]) != "contract"]
    if not executable_ids:
        executable_ids = prior_ids[:]
    tasks.append(
        {
            **base,
            "task_id": f"{prefix}-review",
            "task_type": "join_review",
            "required_rank": str(review.get("required_rank") or "B"),
            "required_skill": str(review.get("required_skill") or "integration_review"),
            "owner_area": "review",
            "status": "blocked",
            "plan_review_status": "approved",
            "sequence_no": len(tasks) + 1,
            "depends_on": executable_ids,
            "output_artifact": "integration_report",
            "title": f"Review: {title}",
            "request": "\n".join(
                [
                    str(planner.get("review_instruction") or "Review upstream artifacts and write review.md plus final-summary.md."),
                    "",
                    f"Quest workspace: {workspace_rel}",
                    "Read upstream artifacts and workspace files.",
                    "If modules mismatch, request bounded fix tasks for the responsible task.",
                    "If all modules align, write review.md and final-summary.md inside the quest workspace.",
                    "Return artifact JSON listing the file(s) you wrote.",
                ]
            ),
        }
    )
    return (
        tasks,
        [
            "Hermes planner skill pack prepared a plan-only task split.",
            f"Template: {planner.get('template') or 'custom'}",
            str(planner.get("summary") or "Prepared a bounded dynamic worker plan."),
            f"Tasks: {len(tasks)} including join_review.",
        ],
        schedule_quest_wake_profiles(quest_workspace.parents[1], runtime),
    )


def read_tail(path: Path, max_lines: int = 80, max_chars: int = 12000) -> dict[str, Any]:
    if not path.is_file():
        return {
            "path": path.as_posix(),
            "exists": False,
            "lines": [],
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        text = text[-max_chars:]
    return {
        "path": path.as_posix(),
        "exists": True,
        "bytes": path.stat().st_size,
        "lines": text.splitlines()[-max_lines:],
    }


def parse_json_object(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def collect_terminal_sessions(workspace: Path, quest_chain_id: str, limit: int = 12) -> list[dict[str, Any]]:
    sessions_dir = workspace / "_runtime" / "guild-worker-agent" / "terminal-sessions"
    if not sessions_dir.is_dir():
        return []
    sessions: list[dict[str, Any]] = []
    for metadata_path in sorted(sessions_dir.glob("*/session.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig", errors="replace"))
        except Exception:
            continue
        if quest_chain_id and str(metadata.get("quest_chain_id") or "") != quest_chain_id:
            continue
        session_dir = metadata_path.parent
        item = dict(metadata)
        item["metadata_path"] = metadata_path.relative_to(workspace).as_posix()
        item["stdout"] = read_tail(session_dir / "stdout.log", max_lines=80, max_chars=16000)
        item["stderr"] = read_tail(session_dir / "stderr.log", max_lines=80, max_chars=8000)
        sessions.append(item)
        if len(sessions) >= limit:
            break
    return sessions


def read_demo_logs(workspace: Path, quest_chain_id: str = "") -> dict[str, Any]:
    dashboard_dir = workspace / "_runtime" / "dashboard"
    worker_dir = workspace / "_runtime" / "guild-worker-agent"
    return {
        "guild_events": read_tail(dashboard_dir / "guild-events.jsonl", max_lines=120, max_chars=24000),
        "dashboard_server_stdout": read_tail(dashboard_dir / "guild-dashboard-server.out.log"),
        "dashboard_server_stderr": read_tail(dashboard_dir / "guild-dashboard-server.err.log"),
        "e2e_demo": read_tail(dashboard_dir / "e2e-demo-run.log"),
        "worker_payloads": [
            {
                "path": path.relative_to(workspace).as_posix(),
                "bytes": path.stat().st_size,
                "modified": int(path.stat().st_mtime),
            }
            for path in sorted(worker_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:12]
        ]
        if worker_dir.is_dir()
        else [],
        "terminal_sessions": collect_terminal_sessions(workspace, quest_chain_id),
    }


def read_runtime_snapshots(workspace: Path, quest_chain_id: str) -> dict[str, Any]:
    quest_dir = workspace / "guild-workspaces" / quest_chain_id if quest_chain_id else None
    files: list[dict[str, Any]] = []
    if quest_dir and quest_dir.is_dir():
        for path in sorted(quest_dir.glob("*")):
            if path.is_file():
                files.append(
                    {
                        "path": path.relative_to(workspace).as_posix(),
                        "bytes": path.stat().st_size,
                        "modified": int(path.stat().st_mtime),
                    }
                )
    return {
        "quest_workspace": str(quest_dir.relative_to(workspace)) if quest_dir and quest_dir.exists() else None,
        "quest_files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    python_exe = workspace / "_runtime" / "research" / "flock" / ".venv" / "Scripts" / "python.exe"
    local_app_data = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    db_path = Path(args.db) if args.db else local_app_data / "hermes" / "flock" / "worker_team.sqlite"
    server = ThreadingHTTPServer(
        (args.host, args.port),
        lambda *handler_args, **handler_kwargs: GuildDashboardServer(
            *handler_args,
            directory=str(workspace),
            **handler_kwargs,
        ),
    )
    server.workspace = str(workspace)  # type: ignore[attr-defined]
    server.python_exe = str(python_exe if python_exe.exists() else "python")  # type: ignore[attr-defined]
    server.db_path = str(db_path)  # type: ignore[attr-defined]
    print(f"Guild dashboard server: http://{args.host}:{args.port}/docs/incubation/guild-dashboard.html")
    server.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
