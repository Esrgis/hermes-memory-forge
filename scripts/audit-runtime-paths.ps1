[CmdletBinding()]
param(
    [string]$ConfigPath = "config\runtime-paths.json",

    [switch]$MeasureSize
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$configFullPath = if ([System.IO.Path]::IsPathRooted($ConfigPath)) {
    $ConfigPath
} else {
    Join-Path $workspace $ConfigPath
}

if (-not (Test-Path -LiteralPath $configFullPath -PathType Leaf)) {
    throw "Missing runtime path config: $configFullPath"
}

function Expand-HermesPath {
    param([Parameter(Mandatory = $true)][string]$Value)

    $expanded = [Environment]::ExpandEnvironmentVariables($Value)
    if ([System.IO.Path]::IsPathRooted($expanded)) {
        return $expanded
    }
    return Join-Path $workspace $expanded
}

function Get-ScopedSize {
    param([Parameter(Mandatory = $true)][string]$LiteralPath)

    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return $null
    }
    $item = Get-Item -LiteralPath $LiteralPath -Force
    if (-not $item.PSIsContainer) {
        return $item.Length
    }
    $bytes = 0
    Get-ChildItem -LiteralPath $LiteralPath -Force -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { $bytes += $_.Length }
    return $bytes
}

$config = Get-Content -LiteralPath $configFullPath -Raw | ConvertFrom-Json
$results = foreach ($entry in $config.paths) {
    $rawPath = [string]$entry.path
    $expanded = Expand-HermesPath -Value $rawPath
    $hasWildcard = $expanded -match '[*?]'
    $matches = if ($hasWildcard) {
        Get-ChildItem -Path $expanded -Force -ErrorAction SilentlyContinue
    } elseif (Test-Path -LiteralPath $expanded -ErrorAction SilentlyContinue) {
        @(Get-Item -LiteralPath $expanded -Force)
    } else {
        @()
    }

    if (-not $matches) {
        [pscustomobject]@{
            id = $entry.id
            role = $entry.role
            cleanup = $entry.cleanup
            path = $expanded
            exists = $false
            link_type = $null
            target = $null
            attributes = $null
            bytes = $null
        }
        continue
    }

    foreach ($match in $matches) {
        [pscustomobject]@{
            id = $entry.id
            role = $entry.role
            cleanup = $entry.cleanup
            path = $match.FullName
            exists = $true
            link_type = $match.LinkType
            target = if ($match.Target) { $match.Target -join ";" } else { $null }
            attributes = [string]$match.Attributes
            bytes = if ($MeasureSize) { Get-ScopedSize -LiteralPath $match.FullName } else { $null }
        }
    }
}

$results | Sort-Object id, path
