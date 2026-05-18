param(
    [Parameter(Mandatory = $true)]
    [string]$VaultPath,

    [datetime]$Date = (Get-Date),

    [switch]$Overwrite
)

$ErrorActionPreference = 'Stop'

$dateString = $Date.ToString('yyyy-MM-dd')
$dailyDir = Join-Path $VaultPath 'Daily'
$dailyPath = Join-Path $dailyDir "$dateString.md"

New-Item -ItemType Directory -Force -Path $dailyDir | Out-Null

if ((Test-Path -LiteralPath $dailyPath) -and -not $Overwrite) {
    Write-Host $dailyPath
    exit 0
}

$content = @"
---
date: $dateString
type: daily
tags: [daily]
---

# Daily - $dateString

## Tasks

## Schedule

## Log

- $($Date.ToString('HH:mm')) - Daily note created.

## Wins

## Context

"@

Set-Content -LiteralPath $dailyPath -Value $content -Encoding UTF8
Write-Host $dailyPath

