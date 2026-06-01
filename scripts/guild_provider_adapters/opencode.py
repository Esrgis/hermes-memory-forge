from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id
from .groq import normalize_json_text


class OpenCodeAdapter(ProviderAdapter):
    name = "opencode"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        executable = find_opencode_executable()
        if not executable:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary="opencode executable was not found on PATH.",
                test_result="failed",
                blocked_reason="provider_missing",
            )

        args = [
            executable,
            "run",
            "--pure",
            "--format",
            "json",
            "--title",
            context.title,
        ]
        model_ref = self._model_ref(context)
        if model_ref:
            args.extend(["--model", model_ref])
        message = sanitize_windows_cmd_message(context.message)
        attached_prompt: Path | None = None
        if len(message) > 6000:
            attached_prompt = write_prompt_attachment(context.workspace, context.title, message)
            message = (
                "Read the attached Guild worker prompt file and return only the requested "
                "artifact JSON. Do not include markdown."
            )
        args.append(message)
        if attached_prompt is not None:
            args.extend(["--file", str(attached_prompt)])

        command_for_log = " ".join(args[1:]).replace(message, "<message>")
        try:
            completed = subprocess.run(
                args,
                cwd=context.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(os.environ.get("OPENCODE_TIMEOUT_SECONDS", "90")),
            )
        except subprocess.TimeoutExpired:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary="opencode timed out before returning provider output.",
                commands_run=[command_for_log],
                test_result="failed",
                blocked_reason="provider_timeout",
            )
        except OSError as exc:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary=f"opencode failed to start: {exc}",
                commands_run=[command_for_log],
                test_result="failed",
                blocked_reason="provider_failed",
            )

        output_lines = []
        if completed.stdout:
            output_lines.extend(completed.stdout.splitlines())
        if completed.stderr:
            output_lines.extend(completed.stderr.splitlines())

        if completed.returncode != 0:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary=f"opencode exited with code {completed.returncode}.",
                commands_run=[command_for_log],
                test_result="failed",
                known_risks=["\n".join(output_lines)],
                blocked_reason="provider_failed",
            )

        return self._parse_events(context, output_lines, command_for_log)

    def _model_ref(self, context: AdapterContext) -> str | None:
        model = context.model or os.environ.get("OPENCODE_MODEL") or "opencode/deepseek-v4-flash-free"
        if not model:
            return None
        if context.provider:
            return f"{context.provider}/{model}"
        return model

    def _parse_events(
        self,
        context: AdapterContext,
        lines: list[str],
        command_for_log: str,
    ) -> AdapterResult:
        text_parts: list[str] = []
        session_id = None
        tokens: Any = None
        error_events: list[Any] = []

        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("sessionID"):
                session_id = event["sessionID"]
            if event.get("type") == "error":
                error_events.append(event)
            if event.get("type") == "text":
                part = event.get("part") or {}
                text = part.get("text")
                if text:
                    text_parts.append(str(text))
            if event.get("type") == "step_finish":
                part = event.get("part") or {}
                if part.get("tokens") is not None:
                    tokens = part["tokens"]

        if error_events:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                session_id=session_id,
                summary="opencode returned error event.",
                commands_run=[command_for_log],
                test_result="failed",
                known_risks=error_events,
                blocked_reason="provider_error_event",
                tokens=tokens,
            )

        return AdapterResult(
            ok=True,
            adapter=context.adapter_name,
            profile=context.profile_name,
            agent_id=agent_id(context),
            session_id=session_id,
            summary="opencode completed a non-interactive run.",
            text=normalize_json_text("\n".join(text_parts)),
            files_changed=[],
            commands_run=[command_for_log],
            test_result="not_run",
            known_risks=[],
            blocked_reason=None,
            tokens=tokens,
        )

def sanitize_windows_cmd_message(value: str | None) -> str:
    message = " ".join((value or "").split())
    return message.replace("|", "/")


def find_opencode_executable() -> str | None:
    for candidate in ("opencode.cmd", "opencode.exe", "opencode"):
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


def write_prompt_attachment(workspace: str, title: str, message: str) -> Path:
    root = Path(workspace) / "_runtime" / "guild-provider-adapters" / "opencode-prompts"
    root.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in title)[:80].strip("-")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = root / f"{stamp}-{safe_title or 'prompt'}.md"
    path.write_text(message, encoding="utf-8")
    return path
