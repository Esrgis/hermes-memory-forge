from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from guild_provider_adapters.base import AdapterContext
    from guild_provider_adapters.capabilities import resolve_capability
    from guild_provider_adapters.registry import get_adapter
else:
    from .base import AdapterContext
    from .capabilities import resolve_capability
    from .registry import get_adapter


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.is_file():
            return path
    joined = ", ".join(str(path) for path in paths)
    raise FileNotFoundError(f"None of these config files exist: {joined}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke a Guild provider adapter.")
    parser.add_argument("--adapter", default="local-dry-run")
    parser.add_argument("--profile", default="builder")
    parser.add_argument("--message", required=True)
    parser.add_argument("--title", default="guild-worker-adapter")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--capability")
    parser.add_argument("--task-type")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    config_root = workspace / "config" / "guild"
    legacy_root = workspace / "docs" / "workers"
    profiles = load_json(first_existing(config_root / "agent-profiles.json", legacy_root / "agent-profiles.json"))
    adapters = load_json(first_existing(config_root / "provider-adapters.json", legacy_root / "provider-adapters.json"))
    cartridges_path = config_root / "model-cartridges.json"
    transports_path = config_root / "provider-transports.json"
    cartridges = load_json(cartridges_path) if cartridges_path.is_file() else {"cartridges": {}}
    transports = load_json(transports_path) if transports_path.is_file() else {"transports": {}}
    capabilities_path = first_existing(
        config_root / "capability-adapters.json",
        legacy_root / "capability-adapters.json",
    )
    capabilities = load_json(capabilities_path) if capabilities_path.is_file() else {}

    profile_name = args.profile or profiles.get("default_profile", "builder")
    adapter_name = args.adapter or adapters.get("default_adapter", "local-dry-run")

    try:
        agent_profile = profiles["profiles"][profile_name]
    except KeyError as exc:
        available = ", ".join(sorted(profiles.get("profiles", {}).keys()))
        raise SystemExit(f"Unknown profile '{profile_name}'. Available profiles: {available}") from exc

    try:
        adapter_config = adapters["adapters"][adapter_name]
    except KeyError as exc:
        available = ", ".join(sorted(adapters.get("adapters", {}).keys()))
        raise SystemExit(f"Unknown adapter '{adapter_name}'. Available adapters: {available}") from exc

    try:
        capability_name, capability_config = resolve_capability(
            requested=args.capability,
            profile_name=profile_name,
            task_type=args.task_type,
            capabilities=capabilities,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    context = AdapterContext(
        adapter_name=adapter_name,
        adapter_config=adapter_config,
        profile_name=profile_name,
        agent_profile=agent_profile,
        message=args.message,
        title=args.title,
        workspace=str(workspace),
        provider=args.provider,
        model=args.model,
        capability_name=capability_name,
        capability_config=capability_config,
        ammo_config=adapters.get("adapters", {}),
        cartridge_config=cartridges.get("cartridges", {}),
        transport_config=transports.get("transports", {}),
    )
    result = get_adapter(adapter_name).invoke(context)
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
