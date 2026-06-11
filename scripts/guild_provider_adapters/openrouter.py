from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id, GUILD_WORKER_SYSTEM_PROMPT
from .groq import normalize_json_text, retry_delay_seconds


class OpenRouterAdapter(ProviderAdapter):
    name = "openrouter"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary="OPENROUTER_API_KEY is not set in this process environment.",
                commands_run=["openrouter chat.completions"],
                test_result="not_run",
                blocked_reason="provider_missing",
            )

        model = context.model or os.environ.get("OPENROUTER_MODEL") or "openai/gpt-oss-120b:free"
        endpoint = os.environ.get(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1/chat/completions",
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
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "HermesGuildCore/0.1",
            "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "http://127.0.0.1"),
            "X-Title": os.environ.get("OPENROUTER_APP_TITLE", "HermesGuildCore"),
        }
        request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        max_attempts = max(1, int(os.environ.get("GUILD_PROVIDER_RETRY_ATTEMPTS", "3")))
        command_label = f"openrouter chat.completions model={model}"
        raw = ""
        for attempt in range(1, max_attempts + 1):
            try:
                with opener.open(request, timeout=120) as response:
                    raw = response.read().decode("utf-8", errors="replace")
                    break
            except urllib.error.HTTPError as exc:
                error_text = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < max_attempts:
                    import time

                    time.sleep(retry_delay_seconds(exc, error_text))
                    continue
                return AdapterResult(
                    ok=False,
                    adapter=context.adapter_name,
                    profile=context.profile_name,
                    agent_id=agent_id(context),
                    summary=f"OpenRouter returned HTTP {exc.code}.",
                    commands_run=[command_label],
                    test_result="failed",
                    known_risks=[safe_error(error_text)],
                    blocked_reason="provider_failed",
                )
            except OSError as exc:
                return AdapterResult(
                    ok=False,
                    adapter=context.adapter_name,
                    profile=context.profile_name,
                    agent_id=agent_id(context),
                    summary=f"OpenRouter request failed: {exc}",
                    commands_run=[command_label],
                    test_result="failed",
                    blocked_reason="provider_failed",
                )
        else:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary=f"OpenRouter request failed after {max_attempts} attempts.",
                commands_run=[command_label],
                test_result="failed",
                blocked_reason="provider_failed",
            )

        try:
            data = json.loads(raw)
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            text = normalize_json_text(str(message.get("content") or ""))
            usage = data.get("usage")
            response_model = data.get("model")
        except (TypeError, ValueError, IndexError) as exc:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary=f"OpenRouter response parse failed: {exc}",
                commands_run=[f"openrouter chat.completions model={model}"],
                test_result="failed",
                known_risks=[safe_error(raw)],
                blocked_reason="provider_failed",
            )

        return AdapterResult(
            ok=True,
            adapter=context.adapter_name,
            profile=context.profile_name,
            agent_id=agent_id(context),
            summary=f"OpenRouter completed chat completion with {response_model or model}.",
            text=text,
            files_changed=[],
            commands_run=[command_label],
            test_result="not_run",
            known_risks=[],
            blocked_reason=None,
            tokens=usage,
        )


def safe_error(value: str) -> str:
    return value.replace(os.environ.get("OPENROUTER_API_KEY", ""), "[REDACTED]")[:2000]

