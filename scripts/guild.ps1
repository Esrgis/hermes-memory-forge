[CmdletBinding()]
param(
    [string]$QuestChainId = "demo-even-random-app",

    [int]$Port = 8781,

    [switch]$NoOpen,

    [switch]$NoExport,

    [switch]$KeepExisting,

    [switch]$HiddenServer
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$openDashboard = Join-Path $workspace "scripts\open-guild-dashboard.ps1"

if (-not (Test-Path -LiteralPath $openDashboard)) {
    throw "Missing dashboard launcher: $openDashboard"
}

$launcherArgs = @{
    QuestChainId = $QuestChainId
    Port = $Port
}
if ($NoOpen) {
    $launcherArgs.NoOpen = $true
}
if ($NoExport) {
    $launcherArgs.NoExport = $true
}
if (-not $KeepExisting) {
    $launcherArgs.StopExisting = $true
}
if (-not $HiddenServer) {
    $launcherArgs.VisibleServer = $true
}

& $openDashboard @launcherArgs
