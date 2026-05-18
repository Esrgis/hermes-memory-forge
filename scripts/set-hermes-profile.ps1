param(
    [ValidateSet('codex-today', 'openrouter-lean')]
    [string]$Profile = 'codex-today'
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
    throw "Hermes CLI not found in PATH."
}

switch ($Profile) {
    'codex-today' {
        hermes config set model.provider openai-codex
        hermes config set model.default gpt-5.5
        hermes config set model.base_url https://chatgpt.com/backend-api/codex
        hermes config set model.api_mode codex_responses
    }
    'openrouter-lean' {
        hermes config set model.provider openrouter
        hermes config set model.default nvidia/nemotron-3-super-120b-a12b:free
        hermes config set model.base_url https://openrouter.ai/api/v1
        hermes config set model.api_mode chat_completions
    }
}

hermes tools disable delegation --platform cli
hermes tools disable moa --platform cli

Write-Host "Hermes profile applied: $Profile"

