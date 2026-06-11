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


def resolve_ammo_ladder(capability_config: dict[str, Any], combo_config: dict[str, Any] | None = None) -> list[str]:
    ladder = capability_config.get("ammo_ladder") or []
    combos = combo_config or {}
    resolved: list[str] = []
    seen_combos: set[str] = set()

    def add_item(value: Any) -> None:
        item = str(value).strip()
        if not item:
            return
        combo_name = item[6:] if item.startswith("combo:") else item
        combo = combos.get(combo_name)
        if combo:
            if combo_name in seen_combos:
                return
            seen_combos.add(combo_name)
            for child in combo.get("items") or []:
                if isinstance(child, dict):
                    add_item(child.get("cartridge") or child.get("combo") or "")
                else:
                    add_item(child)
            return
        resolved.append(item)

    for entry in ladder:
        add_item(entry)
    return resolved
