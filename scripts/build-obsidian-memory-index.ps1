param(
    [Parameter(Mandatory = $true)]
    [string]$VaultPath,

    [int]$MaxChars = 4000,

    [string]$IndexPath
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$script = Join-Path $PSScriptRoot 'obsidian-memory-index.py'
$argsList = @($script)

if (-not [string]::IsNullOrWhiteSpace($IndexPath)) {
    $argsList += @('--index-path', $IndexPath)
}

$argsList += @('build', '--vault-path', $VaultPath, '--max-chars', $MaxChars)
& python @argsList
