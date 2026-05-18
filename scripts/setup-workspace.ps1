param(
    [string]$WorkspacePath = (Get-Location).Path,
    [string]$VaultPath,
    [string]$HermesHome = "$env:LOCALAPPDATA\hermes",
    [switch]$SkipLinks
)

$ErrorActionPreference = 'Stop'

function New-LinkIfMissing {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Target,
        [ValidateSet('Junction', 'SymbolicLink')][string]$Type = 'Junction'
    )

    if (Test-Path -LiteralPath $Path) {
        return
    }

    if (-not (Test-Path -LiteralPath $Target)) {
        Write-Warning "Target missing, skipping link: $Target"
        return
    }

    New-Item -ItemType $Type -Path $Path -Target $Target | Out-Null
}

$WorkspacePath = (Resolve-Path -LiteralPath $WorkspacePath).Path
New-Item -ItemType Directory -Force -Path (Join-Path $WorkspacePath '_runtime') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $WorkspacePath '_hermes') | Out-Null

if (-not $SkipLinks) {
    New-LinkIfMissing -Path (Join-Path $WorkspacePath '_hermes\memories') -Target (Join-Path $HermesHome 'memories')
    New-LinkIfMissing -Path (Join-Path $WorkspacePath '_hermes\sessions') -Target (Join-Path $HermesHome 'sessions')
    New-LinkIfMissing -Path (Join-Path $WorkspacePath '_hermes\logs') -Target (Join-Path $HermesHome 'logs')
    New-LinkIfMissing -Path (Join-Path $WorkspacePath '_hermes\skills') -Target (Join-Path $HermesHome 'skills')
    New-LinkIfMissing -Path (Join-Path $WorkspacePath '_hermes\config.yaml') -Target (Join-Path $HermesHome 'config.yaml') -Type SymbolicLink

    if ($VaultPath) {
        New-LinkIfMissing -Path (Join-Path $WorkspacePath '_obsidian_vault') -Target $VaultPath
    }
}

Write-Host "Workspace prepared at $WorkspacePath"

