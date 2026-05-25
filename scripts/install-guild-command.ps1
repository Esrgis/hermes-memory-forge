[CmdletBinding()]
param(
    [string]$Workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$profilePath = $PROFILE
$profileDir = Split-Path -Parent $profilePath
$guildScript = Join-Path $Workspace "scripts\guild.ps1"

if (-not (Test-Path -LiteralPath $guildScript)) {
    throw "Missing guild command script: $guildScript"
}

if (-not (Test-Path -LiteralPath $profileDir)) {
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
}

$begin = "# BEGIN HermesGuildCore guild command"
$end = "# END HermesGuildCore guild command"
$block = @"
$begin
function guild {
    & '$guildScript' @args
}
$end
"@

$existing = ""
if (Test-Path -LiteralPath $profilePath) {
    $existing = Get-Content -LiteralPath $profilePath -Raw
}

$pattern = "(?s)" + [regex]::Escape($begin) + ".*?" + [regex]::Escape($end)
if ($existing -match $pattern) {
    $updated = [regex]::Replace($existing, $pattern, $block)
} elseif ([string]::IsNullOrWhiteSpace($existing)) {
    $updated = $block + [Environment]::NewLine
} else {
    $updated = $existing.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine + $block + [Environment]::NewLine
}

Set-Content -LiteralPath $profilePath -Value $updated -Encoding UTF8

[pscustomobject]@{
    ok = $true
    profile = $profilePath
    command = "guild"
    target = $guildScript
}
