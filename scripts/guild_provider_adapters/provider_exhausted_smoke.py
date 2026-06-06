from __future__ import annotations

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id


class ProviderExhaustedSmokeAdapter(ProviderAdapter):
    name = "provider-exhausted-smoke"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        return AdapterResult(
            ok=False,
            adapter=context.adapter_name,
            profile=context.profile_name,
            agent_id=agent_id(context),
            summary="Provider-exhausted smoke adapter simulated a retryable provider outage.",
            text="",
            files_changed=[],
            commands_run=["provider-exhausted-smoke"],
            test_result="failed",
            known_risks=["Intentional provider_exhausted result for worker status smoke tests."],
            blocked_reason="provider_exhausted",
        )
