[CmdletBinding()]
param(
    [string]$Adapter = "local-dry-run",

    [string]$Profile = "builder",

    [Parameter(Mandatory = $true)]
    [string]$Message,

    [string]$Title = "guild-worker-adapter",

    [string]$Provider,

    [string]$Model,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$localProviderSecrets = Join-Path $workspace "_runtime\provider-secrets.local.ps1"
$venvPython = Join-Path $workspace "_runtime\research\flock\.venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$adapterRuntime = Join-Path $workspace "scripts\guild_provider_adapters\invoke.py"

if (Test-Path -LiteralPath $localProviderSecrets) {
    . $localProviderSecrets
}

if (-not (Test-Path -LiteralPath $adapterRuntime)) {
    throw "Missing Guild provider adapter runtime: $adapterRuntime"
}

$adapterArgs = @(
    $adapterRuntime,
    "--adapter", $Adapter,
    "--profile", $Profile,
    "--title", $Title,
    "--workspace", $workspace,
    "--message", $Message
)
if ($Provider) {
    $adapterArgs += @("--provider", $Provider)
}
if ($Model) {
    $adapterArgs += @("--model", $Model)
}

$raw = & $python @adapterArgs

if ($LASTEXITCODE -ne 0) {
    throw "Guild provider adapter runtime failed with exit code $LASTEXITCODE. Output: $($raw -join "`n")"
}

if (-not $raw) {
    throw "Guild provider adapter runtime returned no output."
}

if ($Json) {
    $raw
    return
}

$raw | ConvertFrom-Json
