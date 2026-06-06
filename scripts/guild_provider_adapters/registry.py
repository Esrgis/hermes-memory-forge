from __future__ import annotations

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id
from .gemini import GeminiCliAdapter
from .groq import GroqAdapter
from .invalid_output import InvalidOutputAdapter
from .local_dry_run import LocalDryRunAdapter
from .local_file_writer import LocalFileWriterAdapter
from .opencode import OpenCodeAdapter
from .openai_compatible import NineRouterAdapter, OpenAICompatibleAdapter
from .openrouter import OpenRouterAdapter
from .provider_exhausted_smoke import ProviderExhaustedSmokeAdapter


class UnimplementedAdapter(ProviderAdapter):
    def invoke(self, context: AdapterContext) -> AdapterResult:
        return AdapterResult(
            ok=False,
            adapter=context.adapter_name,
            profile=context.profile_name,
            agent_id=agent_id(context),
            summary="Adapter is declared but not implemented by the Guild provider adapter runtime.",
            text="",
            files_changed=[],
            commands_run=[],
            test_result="not_run",
            known_risks=[],
            blocked_reason="adapter_not_implemented",
        )


def get_backend_adapter(name: str) -> ProviderAdapter:
    if name == "local-dry-run":
        return LocalDryRunAdapter()
    if name == "local-file-writer":
        return LocalFileWriterAdapter()
    if name == "invalid-output-smoke":
        return InvalidOutputAdapter()
    if name == "provider-exhausted-smoke":
        return ProviderExhaustedSmokeAdapter()
    if name == "opencode":
        return OpenCodeAdapter()
    if name == "gemini":
        return GeminiCliAdapter()
    if name == "groq":
        return GroqAdapter()
    if name == "openrouter":
        return OpenRouterAdapter()
    if name in {"9router", "nine-router", "nine_router"}:
        return NineRouterAdapter()
    if name in {"openai-compatible", "openai_compatible"}:
        return OpenAICompatibleAdapter()
    return UnimplementedAdapter()


def get_adapter(name: str) -> ProviderAdapter:
    if name in {"auto-ammo", "capability-auto"}:
        from .ladder import AmmoLadderAdapter

        return AmmoLadderAdapter()
    return get_backend_adapter(name)
