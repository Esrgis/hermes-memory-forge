from __future__ import annotations

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id


class InvalidOutputAdapter(ProviderAdapter):
    name = "invalid-output-smoke"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        return AdapterResult(
            ok=True,
            adapter=context.adapter_name,
            profile=context.profile_name,
            agent_id=agent_id(context),
            summary="Invalid-output smoke adapter returned malformed artifact JSON.",
            text='{"ok":true,"summary":"missing required fields"}',
            files_changed=[],
            commands_run=[],
            test_result="not_required",
            known_risks=["Intentional malformed output for validator smoke tests."],
            blocked_reason=None,
        )
