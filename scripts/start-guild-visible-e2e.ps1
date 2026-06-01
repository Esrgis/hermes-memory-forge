[CmdletBinding()]
param(
    [int]$StartPort = 8830,
    [int]$EndPort = 8849
)

$ErrorActionPreference = "Stop"
Remove-Module PSReadLine -Force -ErrorAction SilentlyContinue

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$dashboardScript = Join-Path $workspace "scripts\open-guild-dashboard.ps1"
$dashboardJson = Join-Path $workspace "_runtime\dashboard\guild-dashboard.json"
$dashboardDir = Split-Path -Parent $dashboardJson
$dbPath = Join-Path $env:TEMP "hermes-guild-doubleclick-demo.sqlite"

function Test-PortFree {
    param([int]$Port)
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

if (Test-Path -LiteralPath $dbPath) {
    Remove-Item -LiteralPath $dbPath -Force
}

New-Item -ItemType Directory -Force -Path $dashboardDir | Out-Null
@{
    schema_version = "guild_dashboard_read_v0"
    task_count = 0
    artifact_count = 0
    status_counts = @{}
    type_counts = @{}
    chains = @()
    tasks = @()
    artifacts = @()
    filters = @{ quest_chain_id = "new-visible-demo" }
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $dashboardJson -Encoding UTF8

$port = $null
foreach ($candidate in $StartPort..$EndPort) {
    if (Test-PortFree -Port $candidate) {
        $port = $candidate
        break
    }
}
if (-not $port) {
    throw "No free dashboard port found from $StartPort to $EndPort."
}

Write-Host "Hermes Guild visible E2E launcher" -ForegroundColor Cyan
Write-Host "Workspace: $workspace"
Write-Host "DB: $dbPath"
Write-Host "Port: $port"
Write-Host ""
Write-Host "Opening UI. In the browser, type a prompt and click Assign to Guild." -ForegroundColor Yellow
Write-Host "That will open 4 terminals: Hermes finalizer + worker-a + worker-b + worker-c." -ForegroundColor Yellow
Write-Host "Provider bugs may still appear; this launcher is the visible demo artifact." -ForegroundColor DarkYellow
Write-Host ""
Write-Host "Copyable demo prompt:" -ForegroundColor Cyan
Write-Host @"
Make a tiny visible E2E app demo artifact for Hermes Guild.
Split the work into 3 worker tracks:
1. Requirements: write the user story, acceptance criteria, and scoped output plan.
2. Risk analysis: list provider/runtime risks and the fallback behavior for the demo.
3. Verification: write a checklist proving files were produced and the final artifact is usable.
Each worker must write its assigned markdown file in the quest workspace. Hermes should finalize review.md, final-summary.md, and final-artifact.json.
"@ -ForegroundColor White
Write-Host ""

& $dashboardScript -Port $port -QuestChainId "new-visible-demo" -DbPath $dbPath -NoExport

Write-Host ""
Write-Host "Dashboard is running. Leave this launcher window open while demoing." -ForegroundColor Green
Write-Host "URL: http://127.0.0.1:$port/docs/incubation/guild-dashboard.html"

$reloadUrl = "http://127.0.0.1:$port/docs/incubation/guild-dashboard.html?reload=$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
Start-Process $reloadUrl | Out-Null
