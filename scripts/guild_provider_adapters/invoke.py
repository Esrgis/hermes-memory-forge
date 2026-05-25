from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from guild_provider_adapters.base import AdapterContext
    from guild_provider_adapters.registry import get_adapter
else:
    from .base import AdapterContext
    from .registry import get_adapter


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke a Guild provider adapter.")
    parser.add_argument("--adapter", default="local-dry-run")
    parser.add_argument("--profile", default="builder")
    parser.add_argument("--message", required=True)
    parser.add_argument("--title", default="guild-worker-adapter")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--provider")
    parser.add_argument("--model")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    profiles = load_json(workspace / "docs" / "workers" / "agent-profiles.json")
    adapters = load_json(workspace / "docs" / "workers" / "provider-adapters.json")

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
    )
    result = get_adapter(adapter_name).invoke(context)
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
