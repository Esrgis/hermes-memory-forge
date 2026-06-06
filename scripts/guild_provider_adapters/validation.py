from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import AdapterContext, AdapterResult


REQUIRED_ARTIFACT_FIELDS = {
    "ok",
    "summary",
    "files_changed",
    "commands_run",
    "test_result",
    "known_risks",
    "blocked_reason",
}

ALLOWED_TEST_RESULTS = {"passed", "failed", "not_run", "not_required"}
TEST_RESULT_ALIASES = {
    "pass": "passed",
    "passed": "passed",
    "fail": "failed",
    "failed": "failed",
    "notrun": "not_run",
    "not_run": "not_run",
    "skip": "not_run",
    "skipped": "not_run",
    "not_required": "not_required",
    "notrequired": "not_required",
    "not-needed": "not_required",
    "not_needed": "not_required",
    "not applicable": "not_required",
    "n/a": "not_required",
}

GENERIC_COMMAND_PATTERNS = (
    "terraform ",
    "go test",
    "go vet",
    "kubectl ",
    "docker build",
    "pnpm ",
    "npm ",
    "npm test",
    "pytest",
)


@dataclass
class ArtifactValidation:
    valid: bool
    blocked_reason: str | None = None
    errors: list[str] = field(default_factory=list)
    output: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "blocked_reason": self.blocked_reason,
            "errors": self.errors,
            "output": self.output,
        }


def extract_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fence = re.match(r"(?s)^```(?:json)?\s*(.*?)\s*```$", candidate)
    if fence:
        candidate = fence.group(1).strip()
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        parsed = json.loads(escape_unquoted_string_quotes(candidate))
    if not isinstance(parsed, dict):
        raise ValueError("artifact JSON root must be an object")
    return parsed


def escape_unquoted_string_quotes(value: str) -> str:
    """Repair provider JSON with bare quotes inside string values."""
    chars: list[str] = []
    in_string = False
    escaped = False
    length = len(value)
    for index, char in enumerate(value):
        if escaped:
            chars.append(char)
            escaped = False
            continue
        if char == "\\" and in_string:
            chars.append(char)
            escaped = True
            continue
        if in_string and char == "\n":
            chars.append("\\n")
            continue
        if in_string and char == "\r":
            chars.append("\\r")
            continue
        if in_string and char == "\t":
            chars.append("\\t")
            continue
        if char != '"':
            chars.append(char)
            continue

        if not in_string:
            in_string = True
            chars.append(char)
            continue

        lookahead = index + 1
        while lookahead < length and value[lookahead].isspace():
            lookahead += 1
        next_char = value[lookahead] if lookahead < length else ""
        if next_char in {":", ",", "}", "]", ""}:
            in_string = False
            chars.append(char)
        else:
            chars.append('\\"')
    return "".join(chars)


def normalize_string_list(value: Any) -> list[str] | Any:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return value


def normalize_file_outputs(value: Any) -> list[dict[str, Any]] | Any:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return value
    return value


def normalize_test_result(value: Any) -> Any:
    text = str(value or "").strip().lower()
    if not text:
        return value
    return TEST_RESULT_ALIASES.get(text, value)


def normalize_artifact_output(output: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(output)
    if normalized.get("ok") is True:
        blocked_reason = normalized.get("blocked_reason")
        if "blocked_reason" not in normalized or (
            isinstance(blocked_reason, str) and not blocked_reason.strip()
        ):
            normalized["blocked_reason"] = None
    normalized["test_result"] = normalize_test_result(normalized.get("test_result"))
    for array_field in ("files_changed", "commands_run", "known_risks"):
        if array_field in normalized:
            normalized[array_field] = normalize_string_list(normalized[array_field])
    if "file_outputs" in normalized:
        normalized["file_outputs"] = normalize_file_outputs(normalized["file_outputs"])
    return normalized


def significant_terms(value: str) -> list[str]:
    stop = {
        "return",
        "only",
        "compact",
        "artifact",
        "json",
        "with",
        "true",
        "summary",
        "files",
        "changed",
        "commands",
        "run",
        "test",
        "result",
        "known",
        "risks",
        "blocked",
        "reason",
        "this",
        "that",
        "the",
        "and",
        "for",
        "not",
        "null",
        "none",
        "provider",
        "lab",
        "smoke",
        "worker",
        "guild",
    }
    terms: list[str] = []
    for term in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", value.lower()):
        if term not in stop and term not in terms:
            terms.append(term)
    return terms[:12]


def configured_terms(context: AdapterContext, key: str) -> list[str]:
    values = context.adapter_config.get(key) or context.capability_config.get(key) or []
    if isinstance(values, str):
        values = [values]
    terms: list[str] = []
    for item in values:
        for part in str(item).split(","):
            term = part.strip().lower()
            if term:
                terms.append(term)
    return terms


def extract_current_task(message: str) -> dict[str, Any]:
    marker = "Current GuildTask JSON:"
    start = message.find(marker)
    if start < 0:
        return {}
    candidate = message[start + len(marker) :].lstrip()
    if not candidate.startswith("{"):
        return {}

    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(candidate)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(text_values(item))
        return values
    if isinstance(value, dict):
        values = []
        for item in value.values():
            values.extend(text_values(item))
        return values
    return [str(value)]


def output_search_text(output: dict[str, Any]) -> str:
    values: list[str] = []
    for field_name in ("summary", "commands_run", "files_changed", "file_outputs"):
        values.extend(text_values(output.get(field_name)))
    return "\n".join(values).lower()


def default_expected_terms(context: AdapterContext, task: dict[str, Any]) -> list[str]:
    task_type = str(context.task_type or task.get("task_type") or "").lower()
    capability = str(context.capability_name or "").lower()
    if task_type == "join_review" or capability == "join-review-worker":
        return ["review.md", "final-summary.md", "integration review", "join review"]

    task_text = "\n".join(
        str(task.get(key) or "")
        for key in ("task_id", "title", "request", "required_skill", "definition_of_done")
    )
    if not task_text.strip():
        task_text = context.message
    return [
        term
        for term in significant_terms(task_text)
        if term not in {"provider", "artifact", "schema", "compact"}
    ][:4]


def validate_artifact_text(context: AdapterContext, result: AdapterResult) -> ArtifactValidation:
    if not result.ok:
        return ArtifactValidation(
            valid=False,
            blocked_reason=result.blocked_reason or "adapter_failed",
            errors=["Adapter did not report ok=true."],
        )
    if result.blocked_reason:
        return ArtifactValidation(
            valid=False,
            blocked_reason=result.blocked_reason,
            errors=["Adapter reported blocked_reason."],
        )
    if not result.text.strip():
        return ArtifactValidation(
            valid=False,
            blocked_reason="invalid_adapter_output",
            errors=["Adapter text is empty; expected artifact JSON."],
        )

    try:
        output = normalize_artifact_output(extract_json_object(result.text))
    except Exception as exc:
        return ArtifactValidation(
            valid=False,
            blocked_reason="invalid_adapter_output",
            errors=[f"Adapter text is not valid artifact JSON: {exc}"],
        )

    errors: list[str] = []
    missing = sorted(REQUIRED_ARTIFACT_FIELDS - set(output))
    for field_name in missing:
        errors.append(f"Missing required artifact field: {field_name}")

    if "ok" in output and not isinstance(output["ok"], bool):
        errors.append("Field ok must be boolean.")
    if "summary" in output and not str(output["summary"]).strip():
        errors.append("Field summary must be a non-empty string.")
    for array_field in ("files_changed", "commands_run", "known_risks"):
        if array_field in output and not isinstance(output[array_field], list):
            errors.append(f"Field {array_field} must be an array.")
    if "file_outputs" in output and not isinstance(output["file_outputs"], list):
        errors.append("Optional file_outputs must be an array when present.")
    if "test_result" in output and str(output["test_result"]) not in ALLOWED_TEST_RESULTS:
        errors.append(
            "Field test_result must be one of: "
            + ", ".join(sorted(ALLOWED_TEST_RESULTS))
            + "."
        )
    if "blocked_reason" in output:
        if output["blocked_reason"] is not None and not isinstance(output["blocked_reason"], str):
            errors.append("Field blocked_reason must be null or string.")
        if isinstance(output["blocked_reason"], str) and not output["blocked_reason"].strip():
            errors.append("Field blocked_reason must be null or a non-empty string.")

    combined = output_search_text(output)
    message_lower = context.message.lower()

    expect_terms = configured_terms(context, "expect_terms")
    if not expect_terms:
        expect_terms = default_expected_terms(context, extract_current_task(context.message))
    if expect_terms and not any(term in combined for term in expect_terms):
        errors.append(
            "Artifact output does not include any expected task term: "
            + ", ".join(expect_terms)
        )

    forbidden_terms = configured_terms(context, "forbidden_terms")
    for pattern in GENERIC_COMMAND_PATTERNS:
        if pattern in combined and pattern not in message_lower:
            forbidden_terms.append(pattern.strip())
    for term in sorted(set(forbidden_terms)):
        if term and term in combined:
            errors.append(f"Artifact output includes forbidden or unrelated term: {term}")

    return ArtifactValidation(
        valid=not errors,
        blocked_reason=None if not errors else "invalid_adapter_output",
        errors=errors,
        output=output,
    )
