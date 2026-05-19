param(
    [string]$Status = "done"
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$blackboard = Join-Path $PSScriptRoot 'blackboard.py'

& python $blackboard checkin-mark game --status $Status
