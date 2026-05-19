param(
    [Parameter(Mandatory = $true)]
    [string]$Query,

    [int]$Limit = 8,

    [string]$IndexPath
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$script = Join-Path $PSScriptRoot 'obsidian-memory-index.py'
$argsList = @($script)

if (-not [string]::IsNullOrWhiteSpace($IndexPath)) {
    $argsList += @('--index-path', $IndexPath)
}

$argsList += @('search', $Query, '--limit', $Limit)
& python @argsList
