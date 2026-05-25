[CmdletBinding()]
param(
    [string]$QuestChainId = "demo-even-random-app",

    [string]$AgentId = "fake-dashboard-worker",

    [ValidateSet("S", "A", "B", "C", "D")]
    [string]$AgentRank = "S",

    [string]$Skills = "general",

    [int]$MaxSteps = 1,

    [switch]$Reset,

    [switch]$SeedOnly,

    [switch]$IncludeArtifacts = $true
)

$ErrorActionPreference = "Stop"

# Legacy note (UI demo):
# This script predates the visible worker-terminal loop and overlaps with `start-guild-worker-terminal.ps1`.
# Prefer `open-guild-dashboard.ps1` + `start-guild-worker-terminal.ps1` + `run-guild-worker-agent.ps1` for the current UI-first demo flow.

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $workspace "_runtime\research\flock\.venv\Scripts\python.exe"
$prototype = Join-Path $workspace "_runtime\flock\worker_team_prototype.py"
$jsonPath = Join-Path $workspace "_runtime\dashboard\guild-dashboard.json"
$jsonDir = Split-Path -Parent $jsonPath

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing Python runtime: $python"
}

if (-not (Test-Path -LiteralPath $prototype)) {
    throw "Missing Worker Team prototype: $prototype"
}

$events = @()

if ($Reset) {
    $seed = & $python $prototype seed-demo-chain --quest-chain-id $QuestChainId --reset
    if ($LASTEXITCODE -ne 0) {
        throw "seed-demo-chain failed with exit code $LASTEXITCODE"
    }
    $events += [pscustomobject]@{
        action = "seed-demo-chain"
        result = ($seed | ConvertFrom-Json)
    }
}

if (-not $SeedOnly) {
    $worker = & $python $prototype run-fake-worker `
        --quest-chain-id $QuestChainId `
        --agent-id $AgentId `
        --agent-rank $AgentRank `
        --skills $Skills `
        --max-steps $MaxSteps
    if ($LASTEXITCODE -ne 0) {
        throw "run-fake-worker failed with exit code $LASTEXITCODE"
    }
    $events += [pscustomobject]@{
        action = "run-fake-worker"
        result = ($worker | ConvertFrom-Json)
    }
}

$dashboardArgs = @(
    $prototype,
    "dashboard",
    "--quest-chain-id", $QuestChainId,
    "--include-tasks"
)
if ($IncludeArtifacts) {
    $dashboardArgs += "--include-artifacts"
}
New-Item -ItemType Directory -Force -Path $jsonDir | Out-Null
$dashboardJson = & $python @dashboardArgs
if ($LASTEXITCODE -ne 0) {
    throw "dashboard export failed with exit code $LASTEXITCODE"
}
$dashboardJson | Set-Content -LiteralPath $jsonPath -Encoding UTF8

[pscustomobject]@{
    quest_chain_id = $QuestChainId
    json_path = $jsonPath
    events = $events
} | ConvertTo-Json -Depth 10
