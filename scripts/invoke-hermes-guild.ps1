[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Prompt,

    [string]$Provider,

    [string]$Model,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$runtimeConfigPath = Join-Path $workspace "config\guild\guild-runtime.json"

function Test-HermesPlannerOutput {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Planner,
        [Parameter(Mandatory = $true)]
        [int]$ExpectedTrackCount
    )

    $errors = @()
    foreach ($field in @("ok", "title", "request", "summary", "tracks", "review_instruction", "risks")) {
        if (-not ($Planner.PSObject.Properties.Name -contains $field)) {
            $errors += "Missing required planner field: $field"
        }
    }
    if ($Planner.ok -isnot [bool] -or -not $Planner.ok) {
        $errors += "Field ok must be true boolean."
    }
    if ([string]::IsNullOrWhiteSpace([string]$Planner.title)) {
        $errors += "Field title must be a non-empty string."
    }
    if ([string]::IsNullOrWhiteSpace([string]$Planner.request)) {
        $errors += "Field request must be a non-empty string."
    }
    if ([string]::IsNullOrWhiteSpace([string]$Planner.summary)) {
        $errors += "Field summary must be a non-empty string."
    }
    if (-not ($Planner.tracks -is [System.Collections.IEnumerable]) -or $Planner.tracks -is [string]) {
        $errors += "Field tracks must be an array."
    } elseif (@($Planner.tracks).Count -ne $ExpectedTrackCount) {
        $errors += "Field tracks must contain exactly $ExpectedTrackCount items."
    }
    if ([string]::IsNullOrWhiteSpace([string]$Planner.review_instruction)) {
        $errors += "Field review_instruction must be a non-empty string."
    }
    if ($errors.Count -gt 0) {
        throw "Invalid Hermes planner output: $($errors -join '; ')"
    }
}

if (Test-Path -LiteralPath $runtimeConfigPath) {
    $runtimeConfig = Get-Content -LiteralPath $runtimeConfigPath -Raw | ConvertFrom-Json
    $expectedTrackCount = @($runtimeConfig.module_tracks).Count
} else {
    $expectedTrackCount = 3
}

function Read-CompactFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,

        [int]$MaxChars = 12000
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

$managerBootstrap = Read-CompactFile -RelativePath "docs\workers\HERMES_MANAGER_BOOTSTRAP.md" -MaxChars 14000
$startHere = Read-CompactFile -RelativePath "START_HERE.md" -MaxChars 8000
$runtimeRouter = Read-CompactFile -RelativePath "docs\core\HERMES_RUNTIME_ROUTER.md" -MaxChars 12000
$router = Read-CompactFile -RelativePath "docs\core\HERMES_ROUTER.md" -MaxChars 10000
$providerAdapters = Read-CompactFile -RelativePath "docs\workers\PROVIDER_ADAPTERS.md" -MaxChars 12000
$agentProfiles = Read-CompactFile -RelativePath "config\guild\agent-profiles.json" -MaxChars 8000
$capabilities = Read-CompactFile -RelativePath "config\guild\capability-adapters.json" -MaxChars 10000
$cartridges = Read-CompactFile -RelativePath "config\guild\model-cartridges.json" -MaxChars 8000
$transports = Read-CompactFile -RelativePath "config\guild\provider-transports.json" -MaxChars 8000
$cognition = Read-CompactFile -RelativePath "_obsidian_vault\System\Assistant\Shared\Cognition Reflexes.md" -MaxChars 12000

$fullPrompt = @"
You are Hermes operating as the HermesGuildCore Guild manager.
Use the injected context below as your manager boot contract.
Do not expose secrets. Do not broad crawl. Prefer bounded workspace scripts.
Answer in Vietnamese unless the user explicitly asks otherwise.

=== Hermes Manager Bootstrap ===
$managerBootstrap

=== START_HERE ===
$startHere

=== Runtime Mode Router ===
$runtimeRouter

=== Router ===
$router

=== Provider / Ammo Contract ===
$providerAdapters

=== Agent Profiles ===
$agentProfiles

=== Capability Adapters ===
$capabilities

=== Model Cartridges ===
$cartridges

=== Provider Transports ===
$transports

=== Shared Cognition Reflexes ===
$cognition

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

$raw = & hermes @args
if ($LASTEXITCODE -ne 0) {
    throw "Hermes Guild manager call failed with exit code $LASTEXITCODE. Output: $($raw -join "`n")"
}

if ($Json) {
    $candidate = ($raw -join "`n").Trim()
    if ($candidate -match '(?s)^```(?:json)?\s*(.*?)\s*```$') {
        $candidate = $Matches[1].Trim()
    }
    $start = $candidate.IndexOf('{')
    $end = $candidate.LastIndexOf('}')
    if ($start -lt 0 -or $end -le $start) {
        throw "Hermes planner did not return JSON."
    }
    $planner = $candidate.Substring($start, $end - $start + 1) | ConvertFrom-Json
    Test-HermesPlannerOutput -Planner $planner -ExpectedTrackCount $expectedTrackCount
    $planner | ConvertTo-Json -Depth 20
    return
}

$raw
