[CmdletBinding()]
param(
    [string]$QuestChainId = "demo-even-random-app",
    [string]$OutputPath = "_runtime\dashboard\guild-dashboard.json",
    [switch]$IncludeArtifacts
)

$ErrorActionPreference = "Stop"

$workspace = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$python = Join-Path $workspace "_runtime\research\flock\.venv\Scripts\python.exe"
$prototype = Join-Path $workspace "_runtime\flock\worker_team_prototype.py"
$outputFullPath = Join-Path $workspace $OutputPath
$outputDir = Split-Path -Parent $outputFullPath

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing Python runtime: $python"
}

if (-not (Test-Path -LiteralPath $prototype)) {
    throw "Missing Worker Team prototype: $prototype"
}

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$args = @(
    $prototype,
    "dashboard",
    "--quest-chain-id",
    $QuestChainId,
    "--include-tasks"
)

if ($IncludeArtifacts) {
    $args += "--include-artifacts"
}

$json = & $python @args
if ($LASTEXITCODE -ne 0) {
    throw "Dashboard export failed with exit code $LASTEXITCODE"
}

$json | Set-Content -LiteralPath $outputFullPath -Encoding UTF8
Write-Output $outputFullPath
