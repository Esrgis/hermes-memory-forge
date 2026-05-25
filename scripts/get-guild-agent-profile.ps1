[CmdletBinding()]
param(
    [string]$Profile = "builder",

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$profilePath = Join-Path $workspace "docs\workers\agent-profiles.json"

if (-not (Test-Path -LiteralPath $profilePath)) {
    throw "Missing agent profile file: $profilePath"
}

$config = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json
$selectedName = if ($Profile) { $Profile } else { $config.default_profile }
$profileData = $config.profiles.$selectedName

if (-not $profileData) {
    $available = ($config.profiles.PSObject.Properties.Name -join ", ")
    throw "Unknown profile '$selectedName'. Available profiles: $available"
}

if ($Json) {
    $profileData | ConvertTo-Json -Depth 10
    return
}

[pscustomobject]@{
    profile = $selectedName
    agent_id = $profileData.agent_id
    display_name = $profileData.display_name
    rank = $profileData.rank
    skills = ($profileData.skills -join ",")
    provider_role = $profileData.provider_role
    bootstrap = $profileData.bootstrap
}
