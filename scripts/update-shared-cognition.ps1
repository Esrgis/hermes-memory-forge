[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Summary,

    [string[]]$Reflex = @(),

    [string[]]$Rule = @(),

    [string[]]$NextAction = @(),

    [ValidateSet("codex", "hermes", "manual")]
    [string]$Source = "codex",

    [string]$VaultPath,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if (-not $VaultPath) {
    $VaultPath = Join-Path $workspace "_obsidian_vault"
}

$sharedDir = Join-Path $VaultPath "System\Assistant\Shared"
$targetPath = Join-Path $sharedDir "Cognition Reflexes.md"

function Add-Bullets {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        [string[]]$Items
    )

    if (-not $Items -or $Items.Count -eq 0) {
        return @()
    }
    $lines = @("- ${Label}:")
    foreach ($item in $Items) {
        $clean = ([string]$item).Trim()
        if ($clean) {
            $lines += "  - $clean"
        }
    }
    return $lines
}

if (-not (Test-Path -LiteralPath $sharedDir)) {
    throw "Missing shared memory directory: $sharedDir"
}

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
$entry = @(
    "",
    "## $stamp $Source",
    "",
    "- Summary: $($Summary.Trim())"
)
$entry += Add-Bullets -Label "Reflex" -Items $Reflex
$entry += Add-Bullets -Label "Rule" -Items $Rule
$entry += Add-Bullets -Label "Next action" -Items $NextAction
$entry += ""

if ($DryRun) {
    $entry -join "`n"
    return
}

if (-not (Test-Path -LiteralPath $targetPath)) {
    @(
        "# Cognition Reflexes",
        "",
        "Purpose: compact shared reflex memory for Codex and Hermes.",
        "",
        "Use this file for durable operating reflexes that should survive model changes.",
        "",
        "Rules:",
        "",
        "- Store distilled cognition, not raw logs.",
        "- Prefer stable reflexes, routing rules, failure patterns, and next-session defaults.",
        "- Do not store secrets, tokens, terminal dumps, or full chat transcripts.",
        "- If an entry becomes obsolete, add a correction; do not silently delete audit context.",
        ""
    ) | Set-Content -LiteralPath $targetPath -Encoding UTF8
}

Add-Content -LiteralPath $targetPath -Value ($entry -join "`n") -Encoding UTF8
[pscustomobject]@{
    ok = $true
    path = $targetPath
    source = $Source
    updated_at = (Get-Date).ToUniversalTime().ToString("o")
}
