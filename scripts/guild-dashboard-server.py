from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


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
                    "version": "0.2",
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
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path == "/api/quest/manual":
                self.handle_manual_quest(self.read_json_body())
                return
            if parsed.path == "/api/hermes/quest":
                self.handle_hermes_quest(self.read_json_body())
                return
            if parsed.path == "/api/hermes/finalize":
                self.handle_hermes_finalize(self.read_json_body())
                return
            if parsed.path == "/api/wake":
                self.handle_wake(self.read_json_body())
                return
            if parsed.path == "/api/provider-lab/save-secret":
                self.handle_provider_lab_save_secret(self.read_json_body())
                return
            if parsed.path == "/api/provider-lab/list-models":
                self.handle_provider_lab_list_models(self.read_json_body())
                return
            if parsed.path == "/api/provider-lab/test":
                self.handle_provider_lab_test(self.read_json_body())
                return
            self.send_json({"ok": False, "error": "not_found"}, status=404)
        except Exception as exc:  # Keep local demo errors visible to the UI.
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_dashboard(self, quest_chain_id: str) -> None:
        dashboard = self.export_dashboard(quest_chain_id)
        self.send_json({"ok": True, "dashboard": dashboard})

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
        out_dir = self.workspace / "_runtime" / "dashboard"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "guild-dashboard.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
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

        quest_workspace = create_quest_workspace(self.workspace, quest_chain_id, title, request)
        workspace_glob = f"guild-workspaces/{quest_chain_id}/**"
        effective_allowed_files = join_allowed_files(workspace_glob, allowed_files)

        plan, events, wake_profiles = build_manual_plan(
            quest_chain_id,
            title,
            request,
            effective_allowed_files,
            quest_workspace,
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
        self.send_json(
            {
                "ok": True,
                "quest_chain_id": quest_chain_id,
                "adapter": adapter,
                "router_mode": "manual-router-v0",
                "provider_mode": "local-demo" if adapter == "local-dry-run" else "provider-adapter",
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

        workspace_rel = Path("guild-workspaces") / quest_chain_id
        planner = self.call_hermes_planner(
            title=title,
            request=request,
            quest_chain_id=quest_chain_id,
            workspace_path=workspace_rel.as_posix(),
            adapter=adapter,
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

        plan, events, wake_profiles = build_hermes_plan(
            quest_chain_id=quest_chain_id,
            title=planner_title,
            request=planner_request,
            allowed_files=effective_allowed_files,
            quest_workspace=quest_workspace,
            planner=planner,
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
                },
                "events": events,
                "wake_profiles": wake_profiles,
                "tasks": plan,
                "dashboard": dashboard,
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
    ) -> dict[str, Any]:
        provider = os.environ.get("HERMES_GUILD_HERMES_PROVIDER", "openai-codex")
        model = os.environ.get("HERMES_GUILD_HERMES_MODEL", "gpt-5.5")
        prompt = f"""
You are Hermes, S-rank Guild manager for HermesGuildCore.
Return only compact JSON. No markdown.

Create a bounded worker plan for this UI quest.
Use this fixed runtime contract:
- quest_chain_id: {quest_chain_id}
- quest workspace: {workspace_path}
- workers may write only inside the quest workspace
- split into exactly three parallel build tracks
- Build track A writes build-1.md
- Build track B writes build-2.md
- Build track C writes build-3.md
- Hermes performs the final review after all three worker outputs are done; no fourth worker terminal
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
        args = ["hermes", "--provider", provider, "-m", model, "--ignore-rules", "-z", prompt]
        completed = self.run_cmd(args, timeout=120)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or "Hermes planner failed")
        text = (completed.stdout or "").strip()
        try:
            planner = extract_json_object(text)
        except ValueError as exc:
            raise RuntimeError(f"Hermes planner returned non-JSON output: {text[:1000]}") from exc
        if not planner.get("ok"):
            raise RuntimeError(f"Hermes planner returned ok=false: {planner}")
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
        build_tasks = [
            task
            for task in tasks
            if str(task.get("task_id") or "").endswith(("-build-1", "-build-2", "-build-3"))
        ]
        if len(build_tasks) != 3 or any(task.get("status") != "done" for task in build_tasks):
            self.send_json(
                {
                    "ok": False,
                    "ready": False,
                    "reason": "waiting_for_three_build_workers",
                    "dashboard": dashboard,
                },
                status=409,
            )
            return

        review_tasks = [task for task in tasks if str(task.get("task_type") or "") == "join_review"]
        if not review_tasks:
            raise ValueError("missing join_review task")
        review_task = review_tasks[0]
        if review_task.get("status") == "done":
            self.send_json({"ok": True, "ready": True, "already_done": True, "dashboard": dashboard})
            return

        summaries: list[tuple[str, str]] = []
        missing: list[str] = []
        for index in range(1, 4):
            path = quest_workspace / f"build-{index}.md"
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

        review_path = quest_workspace / "review.md"
        final_path = quest_workspace / "final-summary.md"
        review_path.write_text(
            "\n".join(
                [
                    f"# Hermes Final Review: {quest_chain_id}",
                    "",
                    "Hermes checked the quest workspace after all three worker outputs completed.",
                    "",
                    "## Inputs",
                    "",
                    "- build-1.md",
                    "- build-2.md",
                    "- build-3.md",
                    "",
                    "## Verdict",
                    "",
                    "All required worker files are present inside the bounded quest workspace.",
                    "The final summary is ready for handoff.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        final_path.write_text(
            "\n".join(
                [
                    f"# Final Summary: {quest_chain_id}",
                    "",
                    "Hermes fan-in completed after three worker terminals produced their scoped files.",
                    "",
                    *flatten_worker_summaries(summaries),
                    "",
                    "## Completion",
                    "",
                    "- Workspace created by Hermes.",
                    "- Three worker outputs detected.",
                    "- Hermes final review completed.",
                    "- Blackboard review task marked done.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        payload_dir = self.workspace / "_runtime" / "dashboard"
        payload_dir.mkdir(parents=True, exist_ok=True)
        payload_path = payload_dir / f"{quest_chain_id}-hermes-finalize.json"
        payload = {
            "ok": True,
            "mode": "hermes_finalize_v0",
            "quest_chain_id": quest_chain_id,
            "files_changed": [
                str(review_path.relative_to(self.workspace)),
                str(final_path.relative_to(self.workspace)),
            ],
            "summary": "Hermes verified three worker outputs and wrote final review files.",
        }
        payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.publish_artifact(
            task_id=str(review_task["task_id"]),
            artifact_type=str(review_task.get("output_artifact") or "integration_report"),
            producer_agent_id="hermes-codex",
            summary=f"hermes_finalized_{quest_chain_id}",
            payload_path=payload_path,
        )
        self.set_task_status(str(review_task["task_id"]), "done")
        telegram = self.send_telegram_report(
            "\n".join(
                [
                    "Hermes Guild quest complete",
                    f"Quest: {quest_chain_id}",
                    "Workers: worker-a/opencode, worker-b/openrouter, worker-c/groq",
                    "Files: review.md, final-summary.md",
                    f"Workspace: guild-workspaces/{quest_chain_id}",
                ]
            )
        )
        dashboard = self.export_dashboard(quest_chain_id)
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
                    "powershell",
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
        profiles = body.get("profiles") or ["worker-a", "worker-b", "worker-c"]
        dry_run = bool(body.get("dry_run"))
        interval_seconds = str(int(body.get("interval_seconds") or 2))
        worker_adapters = resolve_worker_adapters(adapter, profiles)
        launched = []
        for index, profile in enumerate(profiles):
            worker_adapter = worker_adapters[index]
            args = [
                "powershell",
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
            ]
            if dry_run:
                args.append("-DryRun")
            completed = self.run_cmd(args)
            launched.append(
                {
                    "profile": profile,
                    "adapter": worker_adapter,
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
                "models": models,
                "dynamic": dynamic,
            }
        )

    def handle_provider_lab_test(self, body: dict[str, Any]) -> None:
        cartridge = str(body.get("cartridge") or "").strip()
        model = str(body.get("model") or "").strip()
        capability = str(body.get("capability") or "deterministic-smoke").strip()
        profile = str(body.get("profile") or "builder").strip()
        if not cartridge:
            raise ValueError("cartridge is required")
        message = (
            "Return only compact artifact JSON with ok=true, summary, files_changed, "
            "commands_run, test_result, known_risks, and blocked_reason. This is a Provider Lab smoke test."
        )
        args = [
            "powershell",
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
            "provider-lab-smoke",
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
        completed = self.run_cmd(args, timeout=180)
        payload = parse_json_or_text(completed.stdout)
        self.send_json(
            {
                "ok": completed.returncode == 0,
                "returncode": completed.returncode,
                "cartridge": cartridge,
                "capability": capability,
                "result": payload,
                "stderr": completed.stderr,
            },
            status=200 if completed.returncode == 0 else 502,
        )


def slugify(value: str) -> str:
    text = "".join(char.lower() if char.isalnum() else "-" for char in value)
    parts = [part for part in text.split("-") if part]
    return "-".join(parts[:8]) or "manual-quest"


def load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_guild_provider_config(workspace: Path) -> dict[str, Any]:
    root = workspace / "config" / "guild"
    return {
        "transports": load_json_file(root / "provider-transports.json", {"transports": {}}).get("transports", {}),
        "cartridges": load_json_file(root / "model-cartridges.json", {"cartridges": {}}).get("cartridges", {}),
        "capabilities": load_json_file(root / "capability-adapters.json", {"capabilities": {}}).get("capabilities", {}),
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


def list_provider_models(workspace: Path, transport_name: str, transport: dict[str, Any]) -> dict[str, Any]:
    if transport_name == "local-dry-run":
        return {"ok": True, "source": "deterministic", "models": [{"id": "local-dry-run", "source": "deterministic"}]}
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
    api_key = next((read_provider_secret_value(workspace, key) for key in env_keys if read_provider_secret_value(workspace, key)), None)
    if not api_key:
        return {"ok": False, "reason": "provider_missing", "missing_env_keys": env_keys}
    try:
        if transport_name == "openrouter-http":
            request = urllib.request.Request(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            return {
                "ok": True,
                "source": "openrouter",
                "models": [{"id": item.get("id"), "source": "openrouter"} for item in data.get("data", []) if item.get("id")],
            }
        if transport_name == "groq-http":
            request = urllib.request.Request(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            return {
                "ok": True,
                "source": "groq",
                "models": [{"id": item.get("id"), "source": "groq"} for item in data.get("data", []) if item.get("id")],
            }
        if transport_name == "gemini-api":
            url = "https://generativelanguage.googleapis.com/v1beta/models?" + urllib.parse.urlencode({"key": api_key})
            with urllib.request.urlopen(url, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            return {
                "ok": True,
                "source": "gemini",
                "models": [
                    {"id": str(item.get("name") or "").replace("models/", ""), "source": "gemini"}
                    for item in data.get("models", [])
                    if item.get("name")
                ],
            }
    except Exception as exc:
        return {"ok": False, "reason": "provider_failed", "error": str(exc)}
    return {"ok": False, "reason": "list_models_not_supported"}


def parse_json_or_text(text: str) -> Any:
    value = (text or "").strip()
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value[-4000:]}


def resolve_worker_adapters(adapter: str, profiles: list[Any]) -> list[str]:
    if adapter not in {"auto-rank", "rank-auto", "auto"}:
        return [adapter for _ in profiles]

    # auto-rank is a demo distribution policy; auto-ammo is the provider fallback loader.
    build_ladder = ["opencode", "openrouter", "groq"]
    build_index = 0
    result: list[str] = []
    for profile in profiles:
        name = str(profile)
        if name == "reviewer":
            result.append("groq")
        elif name == "tester":
            result.append("openrouter")
        else:
            result.append(build_ladder[min(build_index, len(build_ladder) - 1)])
            build_index += 1
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
                "- `build-1.md`",
                "- `build-2.md`",
                "- `build-3.md`",
                "- `review.md` from Hermes final check",
                "- `final-summary.md` from Hermes final check",
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
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    prefix = quest_chain_id.replace("quest-", "", 1)
    workspace_rel = quest_workspace.as_posix()
    worker_request = "\n".join(
        [
            request,
            "",
            f"Quest workspace: {workspace_rel}",
            "Write your visible deliverable inside the quest workspace.",
            "Build track A writes build-1.md; build track B writes build-2.md; build track C writes build-3.md; review writes review.md and final-summary.md.",
            "Return artifact JSON listing the file(s) you wrote.",
        ]
    )
    base = {
        "quest_chain_id": quest_chain_id,
        "allowed_files": allowed_files,
    }
    parallel_titles = [
        "Build track A",
        "Build track B",
        "Build track C",
    ]
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
            "request": worker_request,
        },
        *[
            {
                **base,
                "task_id": f"{prefix}-build-{index}",
                "task_type": "execution",
                "required_rank": "C",
                "required_skill": "general",
                "owner_area": "implementation",
                "status": "blocked",
                "plan_review_status": "approved",
                "sequence_no": index + 1,
                "depends_on": [f"{prefix}-spec"],
                "output_artifact": f"implementation_result_{index}",
                "title": f"{track}: {title}",
                "request": worker_request,
            }
            for index, track in enumerate(parallel_titles, start=1)
        ],
        {
            **base,
            "task_id": f"{prefix}-review",
            "task_type": "join_review",
            "required_rank": "B",
            "required_skill": "integration_review",
            "owner_area": "review",
            "status": "blocked",
            "plan_review_status": "approved",
            "sequence_no": 5,
            "depends_on": [f"{prefix}-build-{index}" for index in range(1, 4)],
            "output_artifact": "integration_report",
            "title": f"Review: {title}",
            "request": worker_request,
        },
    ]
    return (
        tasks,
        [
            "Hermes Guild router received the prompt.",
            "Applied temporary manual-router v0 split: spec -> three parallel build tracks -> review.",
            "Prepared parallel worker claims and join-review gate.",
        ],
        ["worker-a", "worker-b", "worker-c"],
    )


def build_hermes_plan(
    *,
    quest_chain_id: str,
    title: str,
    request: str,
    allowed_files: str,
    quest_workspace: Path,
    planner: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    tracks = list(planner.get("tracks") or [])
    while len(tracks) < 3:
        idx = len(tracks) + 1
        tracks.append(
            {
                "id": chr(ord("A") + idx - 1),
                "title": f"Build track {chr(ord('A') + idx - 1)}",
                "instruction": request,
            }
        )
    tracks = tracks[:3]
    prefix = quest_chain_id.replace("quest-", "", 1)
    workspace_rel = quest_workspace.as_posix()
    base = {
        "quest_chain_id": quest_chain_id,
        "allowed_files": allowed_files,
    }

    def worker_request(index: int, track: dict[str, Any]) -> str:
        return "\n".join(
            [
                str(track.get("instruction") or request),
                "",
                f"Quest workspace: {workspace_rel}",
                f"Write your visible deliverable to build-{index}.md inside the quest workspace.",
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
                "task_id": f"{prefix}-build-{index}",
                "task_type": "execution",
                "required_rank": "C",
                "required_skill": "general",
                "owner_area": "implementation",
                "status": "blocked",
                "plan_review_status": "approved",
                "sequence_no": index + 1,
                "depends_on": [f"{prefix}-spec"],
                "output_artifact": f"implementation_result_{index}",
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
            "required_rank": "B",
            "required_skill": "integration_review",
            "owner_area": "review",
            "status": "blocked",
            "plan_review_status": "approved",
            "sequence_no": 5,
            "depends_on": [f"{prefix}-build-{index}" for index in range(1, 4)],
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
        ["worker-a", "worker-b", "worker-c"],
    )


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
