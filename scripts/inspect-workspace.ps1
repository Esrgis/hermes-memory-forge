[CmdletBinding()]
param(
    [string]$Path = '.',

    [ValidateRange(1, 200)]
    [int]$Limit = 60
)

$ErrorActionPreference = 'Stop'

$resolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction Stop
$rootPath = $resolvedPath.ProviderPath

Write-Output "workspace: $rootPath"
Write-Output ''

Write-Output 'tooling:'
foreach ($tool in @('es', 'fd', 'rg', 'eza', 'bat', 'zoxide')) {
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if ($cmd) {
        Write-Output ("- {0}: {1}" -f $tool, $cmd.Source)
    } else {
        Write-Output ("- {0}: missing" -f $tool)
    }
}

Write-Output ''
Write-Output 'top-level:'
$eza = Get-Command eza -ErrorAction SilentlyContinue
if ($eza) {
    & $eza.Source --group-directories-first --icons=never --color=never -- "$rootPath" | Select-Object -First $Limit
} else {
    Get-ChildItem -LiteralPath $rootPath -Force |
        Sort-Object @{ Expression = { -not $_.PSIsContainer } }, Name |
        Select-Object -First $Limit Mode, Length, LastWriteTime, Name |
        Format-Table -AutoSize | Out-String -Width 180
}

Write-Output ''
Write-Output 'git:'
if (Test-Path -LiteralPath (Join-Path $rootPath '.git')) {
    git -C $rootPath status --short --branch
} else {
    Write-Output '- not a git worktree root'
}
