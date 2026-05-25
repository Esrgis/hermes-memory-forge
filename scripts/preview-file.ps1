[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Path,

    [ValidateRange(1, 2000)]
    [int]$Lines = 120,

    [ValidateRange(1, 1000000)]
    [int]$Start = 1
)

$ErrorActionPreference = 'Stop'

$resolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction Stop
$item = Get-Item -LiteralPath $resolvedPath.ProviderPath -Force

if ($item.PSIsContainer) {
    throw "Preview target is a directory, not a file: $($item.FullName)"
}

$bat = Get-Command bat -ErrorAction SilentlyContinue
if ($bat) {
    $end = $Start + $Lines - 1
    & $bat.Source --paging=never --style=numbers --line-range "$Start`:$end" -- "$($item.FullName)"
    exit $LASTEXITCODE
}

Get-Content -LiteralPath $item.FullName -TotalCount ($Start + $Lines - 1) |
    Select-Object -Skip ($Start - 1)
