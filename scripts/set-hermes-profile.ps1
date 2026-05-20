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


# ==============================================================================
# Memory Configuration
# ==============================================================================

$ObsidianVaultPath = "D:\HermesGuildCore\_obsidian_vault"

Write-Host "Setting HERMES_OBSIDIAN_VAULT to $ObsidianVaultPath..."
# Set the environment variable at the User level for persistence across terminal sessions.
[System.Environment]::SetEnvironmentVariable("HERMES_OBSIDIAN_VAULT", $ObsidianVaultPath, [System.EnvironmentVariableTarget]::User)
Write-Host "HERMES_OBSIDIAN_VAULT has been set at the User level. You may need to restart your terminal for the change to be fully effective everywhere."

# Trigger the Obsidian indexer as mentioned in the original script comments
$IndexerScript = Join-Path $PSScriptRoot "obsidian-memory-index.py"
if (Test-Path $IndexerScript) {
    Write-Host "Running Obsidian memory indexer..."
    python.exe $IndexerScript
    Write-Host "Obsidian memory indexer finished."
} else {
    Write-Warning "Could not find the Obsidian memory indexer script at $IndexerScript."
}

Write-Host "Memory configuration complete."