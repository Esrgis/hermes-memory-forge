from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdapterContext:
    adapter_name: str
    adapter_config: dict[str, Any]
    profile_name: str
    agent_profile: dict[str, Any]
    message: str
    title: str
    workspace: str
    provider: str | None = None
    model: str | None = None
    capability_name: str | None = None
    capability_config: dict[str, Any] = field(default_factory=dict)
    ammo_config: dict[str, Any] = field(default_factory=dict)
    cartridge_config: dict[str, Any] = field(default_factory=dict)
    transport_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterResult:
    ok: bool
    adapter: str
    profile: str
    agent_id: str | None
    summary: str
    text: str = ""
    files_changed: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    test_result: str = "not_run"
    known_risks: list[Any] = field(default_factory=list)
    blocked_reason: str | None = None
    session_id: str | None = None
    tokens: Any = None
    ammo: str | None = None
    transport: str | None = None
    capability: str | None = None
    attempts: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "ok": self.ok,
            "adapter": self.adapter,
            "profile": self.profile,
            "agent_id": self.agent_id,
            "summary": self.summary,
            "text": self.text,
            "files_changed": self.files_changed,
            "commands_run": self.commands_run,
            "test_result": self.test_result,
            "known_risks": self.known_risks,
            "blocked_reason": self.blocked_reason,
        }
        if self.session_id is not None:
            data["session_id"] = self.session_id
        if self.tokens is not None:
            data["tokens"] = self.tokens
        if self.ammo is not None:
            data["ammo"] = self.ammo
        if self.transport is not None:
            data["transport"] = self.transport
        if self.capability is not None:
            data["capability"] = self.capability
        if self.attempts:
            data["attempts"] = self.attempts
        return data


class ProviderAdapter:
    """Base class for one provider backend."""

    name = "base"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        raise NotImplementedError


def agent_id(context: AdapterContext) -> str | None:
    value = context.agent_profile.get("agent_id")
    return str(value) if value is not None else None
