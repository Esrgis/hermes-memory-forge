param(
    [string]$Text,

    [string]$InputFile,

    [string]$Title = "hermes-note",

    [string]$NotepadPath,

    [switch]$DryRun,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Write-Result {
    param([Parameter(Mandatory = $true)][object]$Value)

    if ($Json) {
        $Value | ConvertTo-Json -Depth 6
        return
    }
    $Value
}

function Resolve-NotepadPlusPlus {
    param([string]$ExplicitPath)

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "Notepad++ path not found: $ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    $command = Get-Command notepad++ -ErrorAction SilentlyContinue
    if ($command -and $command.Source) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path ${env:ProgramFiles} "Notepad++\notepad++.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Notepad++\notepad++.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Notepad++\notepad++.exe"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Notepad++.Notepad++_8wekyb3d8bbwe\notepad++.exe"),
        (Join-Path $env:USERPROFILE "scoop\apps\notepadplusplus\current\notepad++.exe")
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Notepad++ executable not found. Install it or pass -NotepadPath."
}

function New-SafeFileName {
    param([Parameter(Mandatory = $true)][string]$Value)

    $name = $Value.Trim()
    if ([string]::IsNullOrWhiteSpace($name)) {
        $name = "hermes-note"
    }
    $name = $name -replace '[^\p{L}\p{Nd}\-_ ]+', '-'
    $name = $name.Trim(" -_")
    if ([string]::IsNullOrWhiteSpace($name)) {
        $name = "hermes-note"
    }
    if ($name.Length -gt 48) {
        $name = $name.Substring(0, 48).Trim(" -_")
    }
    return $name
}

if ([string]::IsNullOrWhiteSpace($Text) -and [string]::IsNullOrWhiteSpace($InputFile)) {
    throw "Provide -Text or -InputFile."
}

if (-not [string]::IsNullOrWhiteSpace($Text) -and -not [string]::IsNullOrWhiteSpace($InputFile)) {
    throw "Use either -Text or -InputFile, not both."
}

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$notepad = Resolve-NotepadPlusPlus -ExplicitPath $NotepadPath

if (-not [string]::IsNullOrWhiteSpace($InputFile)) {
    if (-not (Test-Path -LiteralPath $InputFile -PathType Leaf)) {
        throw "Input file not found: $InputFile"
    }
    $targetFile = (Resolve-Path -LiteralPath $InputFile).Path
    $createdFile = $false
} else {
    $scratch = Join-Path $workspace "_runtime\notepad-plus-plus"
    New-Item -ItemType Directory -Path $scratch -Force | Out-Null
    $safeTitle = New-SafeFileName -Value $Title
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $targetFile = Join-Path $scratch "$stamp-$safeTitle.txt"
    if (-not $DryRun) {
        Set-Content -LiteralPath $targetFile -Value $Text -Encoding UTF8
    }
    $createdFile = $true
}

$result = [pscustomobject]@{
    ok = $true
    dry_run = [bool]$DryRun
    notepad_path = $notepad
    file = $targetFile
    created_file = [bool]($createdFile -and -not $DryRun)
    would_create_file = [bool]($createdFile -and $DryRun)
}

if ($DryRun) {
    Write-Result $result
    exit 0
}

Start-Process -FilePath $notepad -ArgumentList @($targetFile) -WindowStyle Normal | Out-Null
Write-Result $result
