[CmdletBinding()]
param(
    [string]$Adapter = "local-dry-run",

    [string]$Profile = "builder",

    [Parameter(Mandatory = $true)]
    [string]$Message,

    [string]$Title = "guild-worker-adapter",

    [string]$Provider,

    [string]$Model,

    [string]$Capability,

    [string]$TaskType,

    [string[]]$ExpectTerm = @(),

    [string[]]$ForbiddenTerm = @(),

    [switch]$SkipArtifactValidation,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$localProviderSecrets = Join-Path $workspace "_runtime\provider-secrets.local.ps1"
$venvPython = Join-Path $workspace "_runtime\research\flock\.venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$adapterRuntime = Join-Path $workspace "scripts\guild_provider_adapters\invoke.py"
$runtimeRoot = Join-Path $workspace "_runtime\guild-provider-adapter"
$messagePath = Join-Path $runtimeRoot ("message-{0}.txt" -f ([Guid]::NewGuid().ToString("N")))

if (Test-Path -LiteralPath $localProviderSecrets) {
    . $localProviderSecrets
}

if (-not (Test-Path -LiteralPath $adapterRuntime)) {
    throw "Missing Guild provider adapter runtime: $adapterRuntime"
}

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
Set-Content -LiteralPath $messagePath -Value $Message -Encoding UTF8

$adapterArgs = @(
    $adapterRuntime,
    "--adapter", $Adapter,
    "--profile", $Profile,
    "--title", $Title,
    "--workspace", $workspace,
    "--message-file", $messagePath
)
if ($Provider) {
    $adapterArgs += @("--provider", $Provider)
}
if ($Model) {
    $adapterArgs += @("--model", $Model)
}
if ($Capability) {
    $adapterArgs += @("--capability", $Capability)
}
if ($TaskType) {
    $adapterArgs += @("--task-type", $TaskType)
}
foreach ($term in $ExpectTerm) {
    if (-not [string]::IsNullOrWhiteSpace($term)) {
        $adapterArgs += @("--expect-term", $term)
    }
}
foreach ($term in $ForbiddenTerm) {
    if (-not [string]::IsNullOrWhiteSpace($term)) {
        $adapterArgs += @("--forbidden-term", $term)
    }
}
if ($SkipArtifactValidation) {
    $adapterArgs += "--skip-artifact-validation"
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
    Remove-Item -LiteralPath $messagePath -Force -ErrorAction SilentlyContinue
    return
}

try {
    $raw | ConvertFrom-Json
} finally {
    Remove-Item -LiteralPath $messagePath -Force -ErrorAction SilentlyContinue
}
