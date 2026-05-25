[CmdletBinding()]
param(
    [string]$Profile = "builder",

    [ValidateSet("opencode", "gemini", "groq")]
    [string]$Adapter = "opencode",

    [string]$Provider,

    [string]$Model,

    [string]$Message = 'Return exactly this JSON and do not modify files: {"ok":true}',

    [switch]$List,

    [switch]$TestNow,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$profilesPath = Join-Path $workspace "docs\workers\agent-profiles.json"
$adaptersPath = Join-Path $workspace "docs\workers\provider-adapters.json"
$runtimeDir = Join-Path $workspace "_runtime\guild-worker-agent"
$configPath = Join-Path $runtimeDir "provider-selection.json"
$invokeScript = Join-Path $workspace "scripts\invoke-guild-provider-adapter.ps1"

$profilesConfig = Get-Content -LiteralPath $profilesPath -Raw | ConvertFrom-Json
$adaptersConfig = Get-Content -LiteralPath $adaptersPath -Raw | ConvertFrom-Json
$allowedAdapters = @("opencode", "gemini", "groq")

function ConvertTo-Hashtable {
    param([Parameter(Mandatory = $true)]$Value)

    if ($null -eq $Value) {
        return $null
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        $result = [ordered]@{}
        foreach ($property in $Value.PSObject.Properties) {
            $result[$property.Name] = ConvertTo-Hashtable -Value $property.Value
        }
        return $result
    }
    if ($Value -is [System.Collections.IEnumerable] -and $Value -isnot [string]) {
        $items = @()
        foreach ($item in $Value) {
            $items += ConvertTo-Hashtable -Value $item
        }
        return $items
    }
    return $Value
}

function Write-OutputObject {
    param([Parameter(Mandatory = $true)]$Value)

    if ($Json) {
        $Value | ConvertTo-Json -Depth 20
    } else {
        $Value
    }
}

if ($List) {
    $profiles = @($profilesConfig.profiles.PSObject.Properties.Name)
    $adapters = foreach ($adapterName in $allowedAdapters) {
        $adapterData = $adaptersConfig.adapters.$adapterName
        [pscustomobject]@{
            adapter = $adapterName
            kind = $adapterData.kind
            implemented = ($adapterName -in @("opencode", "gemini", "groq"))
            notes = $adapterData.notes
        }
    }
    Write-OutputObject ([pscustomobject]@{
        profiles = $profiles
        adapters = $adapters
        examples = @(
            '.\scripts\configure-guild-worker.ps1 -Profile builder -Adapter opencode -TestNow',
            '.\scripts\configure-guild-worker.ps1 -Profile tester -Adapter gemini -Model gemini-2.5-flash -TestNow',
            '.\scripts\configure-guild-worker.ps1 -Profile builder -Adapter groq -Model openai/gpt-oss-20b -TestNow'
        )
    })
    return
}

$profileData = $profilesConfig.profiles.$Profile
if (-not $profileData) {
    $available = ($profilesConfig.profiles.PSObject.Properties.Name -join ", ")
    throw "Unknown profile '$Profile'. Available profiles: $available"
}

$adapterData = $adaptersConfig.adapters.$Adapter
if (-not $adapterData) {
    $available = ($allowedAdapters -join ", ")
    throw "Unknown adapter '$Adapter'. Available adapters for this config command: $available"
}

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$selection = [ordered]@{
    schema_version = "guild_worker_provider_selection_v0"
    updated_at = (Get-Date).ToUniversalTime().ToString("o")
    profile = $Profile
    agent_id = $profileData.agent_id
    adapter = $Adapter
    provider = if ($Provider) { $Provider } else { $null }
    model = if ($Model) { $Model } else { $null }
    adapter_kind = $adapterData.kind
    implemented = ($Adapter -in @("opencode", "gemini", "groq"))
    config_path = $configPath
    secret_policy = $adapterData.secret_policy
    notes = "Secrets are not stored here. Provider credentials must come from external provider config or environment."
}

$selection | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $configPath -Encoding UTF8

$testResult = $null
if ($TestNow) {
    $testArgs = @{
        Adapter = $Adapter
        Profile = $Profile
        Title = "guild-config-test-$Profile-$Adapter"
        Message = $Message
        Json = $true
    }
    if ($Provider) {
        $testArgs.Provider = $Provider
    }
    if ($Model) {
        $testArgs.Model = $Model
    }
    $rawTest = & $invokeScript @testArgs
    if (-not $rawTest) {
        throw "Provider test returned no output."
    }
    $testResult = $rawTest | ConvertFrom-Json
}

Write-OutputObject ([pscustomobject]@{
    saved = $true
    selection = $selection
    test = $testResult
})
