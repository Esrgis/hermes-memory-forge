from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "scripts"))

from guild_provider_adapters.base import AdapterContext, AdapterResult  # noqa: E402
from guild_provider_adapters.validation import validate_artifact_text  # noqa: E402


def _context() -> AdapterContext:
    return AdapterContext(
        adapter_name="smoke",
        adapter_config={"expect_terms": ["smoke"]},
        profile_name="builder",
        agent_profile={"agent_id": "smoke-worker"},
        message="Return smoke artifact JSON.",
        title="artifact-validation-smoke",
        workspace=str(WORKSPACE),
    )


def _adapter_result(artifact: dict) -> AdapterResult:
    return AdapterResult(
        ok=True,
        adapter="smoke",
        profile="builder",
        agent_id="smoke-worker",
        summary="smoke adapter result",
        text=json.dumps(artifact),
    )


def test_ok_artifact_without_blocked_reason_is_normalized_to_null() -> None:
    artifact = {
        "ok": True,
        "summary": "smoke artifact without blocked_reason",
        "files_changed": [],
        "commands_run": [],
        "test_result": "not_required",
        "known_risks": [],
    }

    validation = validate_artifact_text(_context(), _adapter_result(artifact))

    assert validation.valid, validation.errors
    assert validation.output is not None
    assert "blocked_reason" in validation.output
    assert validation.output["blocked_reason"] is None


def test_ok_artifact_with_blocked_reason_null_stays_valid() -> None:
    artifact = {
        "ok": True,
        "summary": "smoke artifact with null blocked_reason",
        "files_changed": [],
        "commands_run": [],
        "test_result": "not_required",
        "known_risks": [],
        "blocked_reason": None,
    }

    validation = validate_artifact_text(_context(), _adapter_result(artifact))

    assert validation.valid, validation.errors
    assert validation.output is not None
    assert validation.output["blocked_reason"] is None


def test_near_valid_artifact_is_normalized() -> None:
    artifact = {
        "ok": True,
        "summary": "smoke artifact with aliases",
        "files_changed": "guild-workspaces/demo/build-1.md",
        "commands_run": "smoke command",
        "test_result": "pass",
        "known_risks": "minor formatting drift",
        "blocked_reason": "   ",
        "file_outputs": {
            "path": "guild-workspaces/demo/build-1.md",
            "content": "smoke content",
        },
    }

    validation = validate_artifact_text(_context(), _adapter_result(artifact))

    assert validation.valid, validation.errors
    assert validation.output is not None
    assert validation.output["files_changed"] == ["guild-workspaces/demo/build-1.md"]
    assert validation.output["commands_run"] == ["smoke command"]
    assert validation.output["known_risks"] == ["minor formatting drift"]
    assert validation.output["test_result"] == "passed"
    assert validation.output["blocked_reason"] is None
    assert isinstance(validation.output["file_outputs"], list)



def test_tool_call_prose_is_rejected_as_non_artifact_output() -> None:
    text = """I'll verify the Hermes Guild UI/E2E validation by checking files.
<tool_call>execute_command>
<command>ls -la "guild-workspaces/quest-manual-dashboard-task-20260605141838/"</command>
</tool_call>
"""

    validation = validate_artifact_text(
        _context(),
        AdapterResult(
            ok=True,
            adapter="smoke",
            profile="builder",
            agent_id="smoke-worker",
            summary="poolside-style tool call output",
            text=text,
        ),
    )

    assert not validation.valid
    assert validation.blocked_reason == "invalid_adapter_output"
    assert any("not valid artifact JSON" in error for error in validation.errors)


def test_bare_quotes_inside_file_output_content_are_repaired() -> None:
    text = (
        '{"ok": true, '
        '"summary": "smoke artifact with markdown quotes", '
        '"files_changed": ["guild-workspaces/demo/build-1.md"], '
        '"file_outputs": [{"path": "guild-workspaces/demo/build-1.md", '
        '"content": "# smoke\\nThe button says "Retry provider block" before retry.\\n"}], '
        '"commands_run": [], '
        '"test_result": "not_required", '
        '"known_risks": [], '
        '"blocked_reason": null}'
    )

    validation = validate_artifact_text(
        _context(),
        AdapterResult(
            ok=True,
            adapter="smoke",
            profile="builder",
            agent_id="smoke-worker",
            summary="bare quote output",
            text=text,
        ),
    )

    assert validation.valid, validation.errors
    assert validation.output is not None
    assert validation.output["file_outputs"][0]["content"].count('"') == 2


def test_raw_newlines_inside_file_output_content_are_repaired() -> None:
    text = """{
  "ok": true,
  "summary": "smoke artifact with raw multiline content",
  "files_changed": ["guild-workspaces/demo/build-1.md"],
  "file_outputs": [
    {
      "path": "guild-workspaces/demo/build-1.md",
      "content": "# smoke

The route is POST /api/task/retry-blocked.
This content includes smoke evidence."
    }
  ],
  "commands_run": [],
  "test_result": "not_required",
  "known_risks": [],
  "blocked_reason": null
}"""

    validation = validate_artifact_text(
        _context(),
        AdapterResult(
            ok=True,
            adapter="smoke",
            profile="builder",
            agent_id="smoke-worker",
            summary="raw newline output",
            text=text,
        ),
    )

    assert validation.valid, validation.errors
    assert validation.output is not None
    assert "POST /api/task/retry-blocked" in validation.output["file_outputs"][0]["content"]


def _dashboard_server_module():
    path = WORKSPACE / "scripts" / "guild-dashboard-server.py"
    spec = importlib.util.spec_from_file_location("guild_dashboard_server_smoke", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_request_selects_three_part_template() -> None:
    server = _dashboard_server_module()
    config = json.loads((WORKSPACE / "config" / "guild" / "planner-skills.json").read_text(encoding="utf-8"))
    request = """Run a fresh Hermes Guild UI/E2E validation for the artifact schema fix.
Use exactly 3 worker tracks. Workers must produce build-1.md, build-2.md, build-3.md.
Reviewer must produce review.md and final-summary.md. Finalizer must produce final-artifact.json.
"""

    name, template = server.select_planner_template(config, "Manual dashboard task", request)

    assert name == "three-part-local-demo"
    assert [track["output_file"] for track in template["tracks"]] == ["build-1.md", "build-2.md", "build-3.md"]


def test_artifact_worker_routes_include_poolside_for_worker_c() -> None:
    server = _dashboard_server_module()
    routes = server.resolve_worker_routes(
        "auto-rank",
        ["worker-a", "worker-b", "worker-c", "reviewer"],
        runtime={"scheduler": {"provider_policy": "capability_pool"}},
        workspace=WORKSPACE,
    )

    providers = [route["provider"] for route in routes]
    assert providers[:3] == [
        "gemini:gemini-2.5-flash",
        "opencode:deepseek-v4-flash-free",
        "openrouter:poolside-laguna-free",
    ]
    assert providers[3] == "groq:gpt-oss-20b"


if __name__ == "__main__":
    test_ok_artifact_without_blocked_reason_is_normalized_to_null()
    test_ok_artifact_with_blocked_reason_null_stays_valid()
    test_near_valid_artifact_is_normalized()
    test_tool_call_prose_is_rejected_as_non_artifact_output()
    test_bare_quotes_inside_file_output_content_are_repaired()
    test_raw_newlines_inside_file_output_content_are_repaired()
    test_demo_request_selects_three_part_template()
    test_artifact_worker_routes_include_poolside_for_worker_c()
    print("ok: guild artifact validation smoke")
