from __future__ import annotations

import os
import shutil
import subprocess

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id, GUILD_WORKER_SYSTEM_PROMPT
from .groq import normalize_json_text, post_openai_compatible


class GeminiCliAdapter(ProviderAdapter):
    name = "gemini"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            return self._invoke_api(context, api_key)

        executable = shutil.which("gemini")
        if not executable:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary="No GEMINI_API_KEY/GOOGLE_API_KEY is set and gemini executable was not found on PATH.",
                test_result="failed",
                blocked_reason="provider_missing",
            )

        args = [executable, "--prompt", context.message]
        if context.model:
            args.extend(["--model", context.model])

        command_for_log = "gemini --prompt <message>"
        if context.model:
            command_for_log = f"gemini --model {context.model} --prompt <message>"

        try:
            completed = subprocess.run(
                args,
                cwd=context.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "120")),
            )
        except subprocess.TimeoutExpired:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary="gemini timed out before returning provider output.",
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
                summary=f"gemini failed to start: {exc}",
                commands_run=[command_for_log],
                test_result="failed",
                blocked_reason="provider_failed",
            )

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            risks = []
            if stderr:
                risks.append(stderr[:2000])
            if stdout:
                risks.append(stdout[:2000])
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary=f"gemini exited with code {completed.returncode}.",
                commands_run=[command_for_log],
                test_result="failed",
                known_risks=risks,
                blocked_reason="provider_failed",
            )

        return AdapterResult(
            ok=True,
            adapter=context.adapter_name,
            profile=context.profile_name,
            agent_id=agent_id(context),
            summary="gemini completed a non-interactive run.",
            text=normalize_json_text(stdout),
            files_changed=[],
            commands_run=[command_for_log],
            test_result="not_run",
            known_risks=([stderr[:2000]] if stderr else []),
            blocked_reason=None,
        )

    def _invoke_api(self, context: AdapterContext, api_key: str) -> AdapterResult:
        model = context.model or os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
        endpoint = os.environ.get(
            "GEMINI_CHAT_COMPLETIONS_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        )
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        GUILD_WORKER_SYSTEM_PROMPT
                    ),
                },
                {"role": "user", "content": context.message},
            ],
            "temperature": 0,
        }
        return post_openai_compatible(
            context=context,
            endpoint=endpoint,
            api_key=api_key,
            payload=payload,
            provider_label="Gemini",
            command_label=f"gemini openai.chat.completions model={model}",
        )

