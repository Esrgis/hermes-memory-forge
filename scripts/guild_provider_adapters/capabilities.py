from __future__ import annotations

from typing import Any

DEFAULT_CAPABILITY = "code-edit-worker"


def resolve_capability(
    *,
    requested: str | None,
    profile_name: str,
    task_type: str | None,
    capabilities: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    configured = capabilities.get("capabilities", {})
    if requested:
        name = requested
    elif task_type == "join_review":
        name = "join-review-worker"
    elif profile_name in {"tester", "reviewer"} and profile_name in configured:
        name = profile_name
    else:
        name = capabilities.get("default_capability") or DEFAULT_CAPABILITY

    config = configured.get(name)
    if not config:
        available = ", ".join(sorted(configured.keys()))
        raise ValueError(f"Unknown capability '{name}'. Available capabilities: {available}")
    return name, config


def resolve_ammo_ladder(capability_config: dict[str, Any]) -> list[str]:
    ladder = capability_config.get("ammo_ladder") or []
    return [str(item) for item in ladder if str(item).strip()]

