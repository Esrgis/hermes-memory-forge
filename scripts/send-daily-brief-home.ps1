param(
    [string]$LocationName = "Hue",
    [double]$Latitude = 16.4637,
    [double]$Longitude = 107.5909,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$builder = Join-Path $PSScriptRoot 'build-daily-brief.py'
$message = & python $builder --location $LocationName --latitude $Latitude --longitude $Longitude
$message = ($message -join "`n").Trim()

if ([string]::IsNullOrWhiteSpace($message)) {
    throw "Daily brief builder produced empty output."
}

if ($DryRun) {
    $message
    exit 0
}

& "$PSScriptRoot\send-telegram-home.ps1" -Text $message
