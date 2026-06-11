from __future__ import annotations

from .base import AdapterContext, AdapterResult, ProviderAdapter, agent_id
from .capabilities import resolve_ammo_ladder


RETRYABLE_BLOCKS = {
    "adapter_not_implemented",
    "provider_error_event",
    "provider_failed",
    "provider_missing",
    "provider_rate_limited",
    "provider_service_unavailable",
    "provider_timeout",
}


class AmmoLadderAdapter(ProviderAdapter):
    """Capability adapter: keep the gun fixed, try different model ammo."""

    name = "auto-ammo"

    def invoke(self, context: AdapterContext) -> AdapterResult:
        from .registry import get_backend_adapter

        ladder = resolve_ammo_ladder(context.capability_config, context.combo_config)
        if context.provider:
            preferred = str(context.provider)
            if preferred in ladder:
                ladder = [preferred, *[item for item in ladder if item != preferred]]
            else:
                ladder = [preferred]
        if not ladder:
            return AdapterResult(
                ok=False,
                adapter=context.adapter_name,
                profile=context.profile_name,
                agent_id=agent_id(context),
                summary="Capability has no ammo ladder configured.",
                test_result="not_run",
                blocked_reason="provider_exhausted",
                capability=context.capability_name,
            )

        attempts = []
        last_result: AdapterResult | None = None
        for ammo_name in ladder:
            cartridge = context.cartridge_config.get(ammo_name)
            if cartridge:
                transport_name = str(cartridge.get("transport") or "")
                transport = context.transport_config.get(transport_name, {})
                backend_name = str(transport.get("backend_adapter") or transport.get("adapter") or transport_name)
                model = context.model or cartridge.get("model")
                provider = transport.get("provider_arg")
                adapter_config = transport
                display_ammo = ammo_name
            else:
                transport_name = ammo_name
                backend_name = ammo_name
                model = context.model
                provider = None
                adapter_config = context.ammo_config.get(ammo_name, {})
                display_ammo = ammo_name

            ammo_context = AdapterContext(
                adapter_name=backend_name,
                adapter_config=adapter_config,
                profile_name=context.profile_name,
                agent_profile=context.agent_profile,
                message=context.message,
                title=context.title,
                workspace=context.workspace,
                provider=provider,
                model=str(model) if model else None,
                task_type=context.task_type,
                capability_name=context.capability_name,
                capability_config=context.capability_config,
                ammo_config=context.ammo_config,
                cartridge_config=context.cartridge_config,
                transport_config=context.transport_config,
            )
            result = get_backend_adapter(backend_name).invoke(ammo_context)
            result.ammo = display_ammo
            result.transport = transport_name
            result.capability = context.capability_name
            last_result = result
            attempts.append(
                {
                    "ammo": display_ammo,
                    "transport": transport_name,
                    "backend": backend_name,
                    "model": model,
                    "ok": result.ok,
                    "blocked_reason": result.blocked_reason,
                    "summary": result.summary,
                }
            )
            if result.ok and not result.blocked_reason:
                result.adapter = context.adapter_name
                result.attempts = attempts
                return result
            if result.blocked_reason not in RETRYABLE_BLOCKS:
                result.adapter = context.adapter_name
                result.attempts = attempts
                return result

        return AdapterResult(
            ok=False,
            adapter=context.adapter_name,
            profile=context.profile_name,
            agent_id=agent_id(context),
            summary=(
                f"Ammo ladder exhausted after {len(attempts)} attempt(s). "
                f"Last result: {last_result.summary if last_result else 'none'}"
            ),
            commands_run=(last_result.commands_run if last_result else []),
            test_result=(last_result.test_result if last_result else "not_run"),
            known_risks=(last_result.known_risks if last_result else []),
            blocked_reason="provider_exhausted",
            capability=context.capability_name,
            attempts=attempts,
        )
