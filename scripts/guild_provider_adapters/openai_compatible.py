from __future__ import annotations

from dataclasses import replace
import os

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id, GUILD_WORKER_SYSTEM_PROMPT
from .groq import post_openai_compatible


class OpenAICompatibleAdapter(ProviderAdapter):
    name = "openai-compatible"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        env_keys = [str(key) for key in context.adapter_config.get("env_keys") or [] if str(key).strip()]
        api_key = next((os.environ.get(key) for key in env_keys if os.environ.get(key)), None)
        requires_key = bool(context.adapter_config.get("requires_key", True))
        if requires_key and not api_key:
            missing = ", ".join(env_keys) if env_keys else "provider env key"
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary=f"{missing} is not set in this process environment.",
                commands_run=["openai-compatible chat.completions"],
                test_result="not_run",
                blocked_reason="provider_missing",
            )

        endpoint = str(
            context.adapter_config.get("chat_completions_url")
            or context.adapter_config.get("base_url")
            or ""
        ).strip()
        if not endpoint:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary="OpenAI-compatible transport is missing chat_completions_url or base_url.",
                commands_run=["openai-compatible chat.completions"],
                test_result="not_run",
                blocked_reason="provider_missing",
            )
        if endpoint.rstrip("/").endswith("/v1"):
            endpoint = endpoint.rstrip("/") + "/chat/completions"

        model = context.model or context.adapter_config.get("default_model") or "model-required"
        provider_label = str(context.adapter_config.get("label") or context.adapter_config.get("provider") or "OpenAI-compatible")
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
            api_key=api_key or "",
            payload=payload,
            provider_label=provider_label,
            command_label=f"{provider_label} chat.completions model={model}",
        )


class NineRouterAdapter(ProviderAdapter):
    name = "9router"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        transport_name = str(context.adapter_config.get("transport") or "9router-local")
        transport = context.transport_config.get(transport_name)
        if not transport:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary=f"9Router transport '{transport_name}' is not configured.",
                commands_run=["9router chat.completions"],
                test_result="not_run",
                blocked_reason="provider_missing",
            )

        adapter_config = dict(transport)
        if context.adapter_config.get("default_model") and not adapter_config.get("default_model"):
            adapter_config["default_model"] = context.adapter_config["default_model"]
        if context.adapter_config.get("label") and not adapter_config.get("label"):
            adapter_config["label"] = context.adapter_config["label"]

        routed_context = replace(
            context,
            adapter_name="9router",
            adapter_config=adapter_config,
            model=context.model or context.adapter_config.get("default_model"),
        )
        result = OpenAICompatibleAdapter().invoke(routed_context)
        result.adapter = context.adapter_name
        result.transport = transport_name
        return result

