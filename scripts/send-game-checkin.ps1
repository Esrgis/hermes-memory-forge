param(
    [switch]$FollowUp
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$blackboard = Join-Path $PSScriptRoot 'blackboard.py'

if ($FollowUp) {
    $status = (& python $blackboard checkin-status game).Trim()
    if ($status -eq 'done' -or $status -eq 'ok') {
        exit 0
    }
    $message = "Nhac lan 2: diem danh game hom nay chua thay OK. Neu xong, bao Codex/Hermes: mark game checkin ok."
} else {
    & python $blackboard checkin-create game | Out-Null
    $message = "21:00 roi. Diem danh game di. Neu xong, tra loi/bao: mark game checkin ok."
}

& "$PSScriptRoot\send-telegram-home.ps1" -Text $message
