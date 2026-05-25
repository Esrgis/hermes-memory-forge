[CmdletBinding()]
param(
    [string]$Adapter = "local-dry-run",

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$adapterPath = Join-Path $workspace "config\guild\provider-adapters.json"
$legacyAdapterPath = Join-Path $workspace "docs\workers\provider-adapters.json"

if (-not (Test-Path -LiteralPath $adapterPath)) {
    if (Test-Path -LiteralPath $legacyAdapterPath) {
        $adapterPath = $legacyAdapterPath
    } else {
        throw "Missing provider adapter file: $adapterPath"
    }
}

$config = Get-Content -LiteralPath $adapterPath -Raw | ConvertFrom-Json
$selectedName = if ($Adapter) { $Adapter } else { $config.default_adapter }
$adapterData = $config.adapters.$selectedName

if (-not $adapterData) {
    $available = ($config.adapters.PSObject.Properties.Name -join ", ")
    throw "Unknown provider adapter '$selectedName'. Available adapters: $available"
}

if ($Json) {
    $adapterData | ConvertTo-Json -Depth 10
    return
}

[pscustomobject]@{
    adapter = $selectedName
    kind = $adapterData.kind
    secret_policy = $adapterData.secret_policy
    command = $adapterData.command
    intended_profiles = ($adapterData.intended_profiles -join ",")
    notes = $adapterData.notes
}
