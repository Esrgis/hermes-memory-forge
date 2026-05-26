from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id


class LocalFileWriterAdapter(ProviderAdapter):
    name = "local-file-writer"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        task = extract_task(context.message)
        if not task:
            return blocked(context, "missing_task_packet", "Could not parse Current GuildTask JSON.")

        allowed_files = normalize_allowed_files(task.get("allowed_files"))
        output_file = infer_output_file(task)
        if not output_file:
            return blocked(context, "missing_output_file", "Could not infer output file from task request.")

        relative_path = f"guild-workspaces/{task['quest_chain_id']}/{output_file}"
        if not is_allowed(relative_path, allowed_files):
            return blocked(context, "files_outside_allowed_scope", f"Refusing to write outside allowed_files: {relative_path}")

        workspace = Path(context.workspace)
        target = workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_task_file(task, output_file), encoding="utf-8")

        artifact = {
            "ok": True,
            "summary": f"Local file writer produced {relative_path}.",
            "files_changed": [relative_path],
            "commands_run": ["local-file-writer:write_task_output"],
            "test_result": "not_required",
            "known_risks": ["Deterministic smoke output; not model-generated implementation."],
            "blocked_reason": None,
        }
        return AdapterResult(
            ok=True,
            adapter=context.adapter_name,
            profile=context.profile_name,
            agent_id=agent_id(context),
            summary=f"Local file writer wrote {relative_path}.",
            text=json.dumps(artifact, separators=(",", ":")),
            files_changed=[relative_path],
            commands_run=["local-file-writer:write_task_output"],
            test_result="not_required",
            known_risks=["Deterministic smoke output; not model-generated implementation."],
            blocked_reason=None,
        )


def extract_task(message: str) -> dict[str, Any] | None:
    marker = "Current GuildTask JSON:"
    start = message.find(marker)
    if start < 0:
        return None
    tail = message[start + len(marker) :]
    end = tail.find("Return only compact artifact JSON")
    candidate = tail[:end] if end >= 0 else tail
    left = candidate.find("{")
    right = candidate.rfind("}")
    if left < 0 or right <= left:
        return None
    try:
        value = json.loads(candidate[left : right + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def infer_output_file(task: dict[str, Any]) -> str | None:
    request = str(task.get("request") or "")
    match = re.search(r"Write your visible deliverable to\s+([A-Za-z0-9_.-]+)", request)
    if match:
        return match.group(1)
    task_type = str(task.get("task_type") or "")
    if task_type == "join_review":
        return "review.md"
    artifact = str(task.get("output_artifact") or "")
    if artifact.startswith("implementation_result_"):
        return "build-" + artifact.rsplit("_", 1)[-1] + ".md"
    if artifact.startswith("fix_result_"):
        return "build-" + artifact.rsplit("_", 1)[-1] + ".md"
    return None


def is_allowed(relative_path: str, allowed_files: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    for part in allowed_files.split(","):
        pattern = part.strip().replace("\\", "/")
        if not pattern:
            continue
        prefix = pattern.split("*", 1)[0].rstrip("/")
        if prefix and normalized.startswith(prefix):
            return True
    return False


def normalize_allowed_files(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value or "")


def render_task_file(task: dict[str, Any], output_file: str) -> str:
    title = str(task.get("title") or task.get("task_id") or "Guild task")
    lines = [
        f"# {title}",
        "",
        f"- quest_chain_id: `{task.get('quest_chain_id')}`",
        f"- task_id: `{task.get('task_id')}`",
        f"- task_type: `{task.get('task_type')}`",
        f"- required_skill: `{task.get('required_skill')}`",
        f"- output_file: `{output_file}`",
        "",
        "## Deterministic Smoke Output",
        "",
        "This file was produced by `local-file-writer` to verify scoped file output, artifact validation, and final assembly plumbing without using a paid provider.",
        "",
        "## Request",
        "",
        str(task.get("request") or "").strip(),
        "",
    ]
    return "\n".join(lines)


def blocked(context: AdapterContext, reason: str, summary: str) -> AdapterResult:
    artifact = {
        "ok": False,
        "summary": summary,
        "files_changed": [],
        "commands_run": ["local-file-writer:block"],
        "test_result": "not_required",
        "known_risks": [summary],
        "blocked_reason": reason,
    }
    return AdapterResult(
        ok=True,
        adapter=context.adapter_name,
        profile=context.profile_name,
        agent_id=agent_id(context),
        summary=summary,
        text=json.dumps(artifact, separators=(",", ":")),
        files_changed=[],
        commands_run=["local-file-writer:block"],
        test_result="not_required",
        known_risks=[summary],
        blocked_reason=None,
    )
