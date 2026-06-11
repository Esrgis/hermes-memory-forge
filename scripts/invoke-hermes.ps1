[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Prompt,

    [string]$Provider,

    [string]$Model,

    [switch]$NoSessionMemory,

    [switch]$DryRun,

    [switch]$LightMode # Skip heavy prompt injection for faster cold‑start
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "Resolve-HermesCli.ps1")

function Read-CompactFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,

        [int]$MaxChars = 10000
    )

    $path = Join-Path $workspace $RelativePath
    if (-not (Test-Path -LiteralPath $path)) {
        return "[missing: $RelativePath]"
    }
    $text = Get-Content -LiteralPath $path -Raw
    if ($text.Length -le $MaxChars) {
        return $text
    }
    return $text.Substring(0, $MaxChars) + "`n[truncated: $RelativePath]"
}

$startHere = Read-CompactFile -RelativePath "START_HERE.md" -MaxChars 8000
$runtimeRouter = Read-CompactFile -RelativePath "docs\core\HERMES_RUNTIME_ROUTER.md" -MaxChars 12000
$router = Read-CompactFile -RelativePath "docs\core\HERMES_ROUTER.md" -MaxChars 10000
$currentState = Read-CompactFile -RelativePath "_obsidian_vault\System\Assistant\Shared\Current State.md" -MaxChars 8000

$fullPrompt = @"
You are Hermes operating as the user's local-first personal secretary.
Default to Vietnamese. Be concise, practical, and bounded.
Use the runtime router below to decide whether the request is Secretary, Guild Manager, Workstation Action, Memory/Recall, or Guarded Operation.
For Guild Manager requests, tell the caller to use scripts/invoke-hermes-guild.ps1 unless the answer is simple.
Do not expose secrets. Do not broad crawl. Do not store raw chat logs.

=== START_HERE ===
$startHere

=== Shared Current State ===
$currentState

=== Runtime Mode Router ===
$runtimeRouter

=== Routine Router ===
$router

=== User Request ===
$Prompt
"@

$args = @("-z", $fullPrompt)
if ($Provider) {
    $args += @("--provider", $Provider)
}
if ($Model) {
    $args += @("-m", $Model)
}

$hermesCli = Resolve-HermesCli -Workspace $workspace
function Invoke-SessionMemoryHook {
    param([Parameter(Mandatory = $true)][string]$UserPrompt)

    if ($NoSessionMemory) {
        return
    }
    $shortPrompt = $UserPrompt.Trim()
    if ($shortPrompt.Length -gt 160) {
        $shortPrompt = $shortPrompt.Substring(0, 160) + "..."
    }
    try {
        & (Join-Path $PSScriptRoot "close-session-memory.ps1") `
            -Apply `
            -Summary "Hermes Secretary call completed: $shortPrompt" `
            -NextAction @(
                "For status/resume, read shared Current State first.",
                "Use Hermes for secretary/routing/memory; use Codex/direct worker for code-heavy work."
            ) `
            -Risk @(
                "Session memory is distilled; raw chat logs are not stored.",
                "Hermes gateway start/stop remains explicit-approval only."
            ) | Out-Null
    } catch {
        Write-Warning "Session memory hook failed: $($_.Exception.Message)"
    }
}

if ($DryRun) {
    [pscustomobject]@{
        ok = $true
        dry_run = $true
        hermes_cli = $hermesCli
        provider = $Provider
        model = $Model
        session_memory_hook_enabled = -not [bool]$NoSessionMemory
        prompt_chars = $fullPrompt.Length
        injected = @(
            "START_HERE.md",
            "_obsidian_vault/System/Assistant/Shared/Current State.md",
            "docs/core/HERMES_RUNTIME_ROUTER.md",
            "docs/core/HERMES_ROUTER.md"
        )
    }
    return
}

$raw = & $hermesCli @args
if ($LASTEXITCODE -ne 0) {
    throw "Hermes call failed with exit code $LASTEXITCODE. Output: $($raw -join "`n")"
}
Invoke-SessionMemoryHook -UserPrompt $Prompt
$raw
