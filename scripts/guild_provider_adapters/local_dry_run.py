from __future__ import annotations

import json

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id


class LocalDryRunAdapter(ProviderAdapter):
    name = "local-dry-run"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        marker = "[needs_info]"
        if marker in (context.message or ""):
            artifact = {
                "ok": False,
                "summary": f"Blocked: needs_info for {context.title}.",
                "files_changed": [],
                "commands_run": ["local-dry-run:needs_info"],
                "test_result": "not_required",
                "known_risks": ["Dry-run adapter did not perform real task work."],
                "blocked_reason": "needs_info",
            }
            return AdapterResult(
                ok=True,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary="Local dry-run adapter returned needs_info.",
                text=json.dumps(artifact, separators=(",", ":")),
                files_changed=[],
                commands_run=["local-dry-run:needs_info"],
                test_result="not_required",
                known_risks=["Dry-run adapter did not perform real task work."],
                blocked_reason=None,
            )

        artifact = {
            "ok": True,
            "summary": f"Local dry-run completed {context.title} without filesystem changes.",
            "files_changed": [],
            "commands_run": ["local-dry-run:artifact_validation"],
            "test_result": "not_required",
            "known_risks": ["Dry-run adapter does not perform real task work."],
            "blocked_reason": None,
        }
        return AdapterResult(
            ok=True,
            adapter=context.adapter_name,
            profile=context.profile_name,
            agent_id=agent_id(context),
            summary="Local dry-run adapter accepted the message without a model call.",
            text=json.dumps(artifact, separators=(",", ":")),
            files_changed=[],
            commands_run=["local-dry-run:artifact_validation"],
            test_result="not_required",
            known_risks=["Dry-run adapter does not perform real task work."],
            blocked_reason=None,
        )
