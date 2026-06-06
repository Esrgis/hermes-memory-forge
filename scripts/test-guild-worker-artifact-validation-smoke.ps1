[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$worker = Join-Path $workspace "scripts\run-guild-worker-agent.ps1"

$raw = & $worker -ArtifactValidationSelfTest -Json
if (-not $?) {
    throw "artifact validation self-test crashed. Output: $($raw -join "`n")"
}
$result = $raw | ConvertFrom-Json

$ok = [bool]($result.ok `
    -and [bool]$result.missing_blocked_reason.valid `
    -and [bool]$result.null_blocked_reason.valid `
    -and $null -eq $result.missing_blocked_reason.output.blocked_reason `
    -and $null -eq $result.null_blocked_reason.output.blocked_reason)

$out = [pscustomobject]@{
    ok = $ok
    smoke = "worker-artifact-validation"
    missing_blocked_reason = $result.missing_blocked_reason
    null_blocked_reason = $result.null_blocked_reason
    near_valid_artifact = $result.near_valid_artifact
}

$out | ConvertTo-Json -Depth 10
if (-not $ok) {
    exit 1
}
