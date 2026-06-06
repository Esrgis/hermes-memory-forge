[CmdletBinding()]
param(
    [string]$QuestChainId = "demo-even-random-app",
    [string]$OutputPath = "_runtime\dashboard\guild-dashboard.json",
    [string]$DbPath,
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
    $prototype
)

if ($DbPath) {
    $args += @("--db", $DbPath)
}

$args += @(
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

$tempPath = "$outputFullPath.tmp.$PID.$([guid]::NewGuid().ToString('N'))"
$json | Set-Content -LiteralPath $tempPath -Encoding UTF8
$replaced = $false
for ($attempt = 1; $attempt -le 20; $attempt++) {
    try {
        Move-Item -LiteralPath $tempPath -Destination $outputFullPath -Force
        $replaced = $true
        break
    } catch {
        if ($attempt -eq 20) {
            throw
        }
        Start-Sleep -Milliseconds ([Math]::Min(150 * $attempt, 2000))
    }
}
if (-not $replaced) {
    throw "Dashboard export replacement failed: $outputFullPath"
}
Write-Output $outputFullPath
