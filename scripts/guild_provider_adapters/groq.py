from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id


class GroqAdapter(ProviderAdapter):
    name = "groq"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary="GROQ_API_KEY is not set in this process environment.",
                commands_run=["groq chat.completions"],
                test_result="not_run",
                blocked_reason="provider_missing",
            )

        model = context.model or os.environ.get("GROQ_MODEL") or "openai/gpt-oss-20b"
        endpoint = os.environ.get(
            "GROQ_CHAT_COMPLETIONS_URL",
            "https://api.groq.com/openai/v1/chat/completions",
        )
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only compact JSON matching the worker artifact schema. "
                        "Do not include markdown fences."
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
            provider_label="Groq",
            command_label=f"groq chat.completions model={model}",
        )


def post_openai_compatible(
    *,
    context: AdapterContext,
    endpoint: str,
    api_key: str,
    payload: dict,
    provider_label: str,
    command_label: str,
) -> AdapterResult:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "HermesGuildCore/0.1",
        },
        method="POST",
    )

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    max_attempts = max(1, int(os.environ.get("GUILD_PROVIDER_RETRY_ATTEMPTS", "3")))
    error_text = ""
    raw = ""
    for attempt in range(1, max_attempts + 1):
        try:
            with opener.open(
                request,
                timeout=int(os.environ.get("GUILD_PROVIDER_TIMEOUT_SECONDS", "120")),
            ) as response:
                raw = response.read().decode("utf-8", errors="replace")
                break
        except urllib.error.HTTPError as exc:
            error_text = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < max_attempts:
                time.sleep(retry_delay_seconds(exc, error_text))
                continue
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary=f"{provider_label} returned HTTP {exc.code}.",
                commands_run=[command_label],
                test_result="failed",
                known_risks=[safe_error(error_text, api_key)],
                blocked_reason="provider_failed",
            )
        except OSError as exc:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary=f"{provider_label} request failed: {exc}",
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
            summary=f"{provider_label} request failed after {max_attempts} attempts.",
            commands_run=[command_label],
            test_result="failed",
            known_risks=[safe_error(error_text, api_key)] if error_text else [],
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
            summary=f"{provider_label} response parse failed: {exc}",
            commands_run=[command_label],
            test_result="failed",
            known_risks=[safe_error(raw, api_key)],
            blocked_reason="provider_failed",
        )

    return AdapterResult(
        ok=True,
        adapter=context.adapter_name,
        profile=context.profile_name,
        agent_id=agent_id(context),
        summary=f"{provider_label} completed chat completion with {response_model or payload.get('model')}.",
        text=text,
        files_changed=[],
        commands_run=[command_label],
        test_result="not_run",
        known_risks=[],
        blocked_reason=None,
        tokens=usage,
    )


def safe_error(value: str, api_key: str | None) -> str:
    result = value
    if api_key:
        result = result.replace(api_key, "[REDACTED]")
    return result[:2000]


def retry_delay_seconds(exc: urllib.error.HTTPError, error_text: str) -> float:
    header = exc.headers.get("Retry-After")
    if header:
        try:
            return min(15.0, max(0.5, float(header)))
        except ValueError:
            pass
    match = re.search(r"try again in\s+([0-9.]+)s", error_text, flags=re.IGNORECASE)
    if match:
        return min(15.0, max(0.5, float(match.group(1)) + 0.25))
    return 2.0


def normalize_json_text(value: str) -> str:
    text = value.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].strip().startswith("```"):
        if lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return text
