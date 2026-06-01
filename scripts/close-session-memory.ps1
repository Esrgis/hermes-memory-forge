[CmdletBinding(DefaultParameterSetName = "DryRun")]
param(
    [string]$Summary = "",

    [string[]]$NextAction = @(),

    [string[]]$Risk = @(),

    [string]$VaultPath,

    [string]$ConfigPath = "config\session-memory.json",

    [ValidateSet("codex", "hermes", "manual")]
    [string]$Source = "codex",

    [Parameter(ParameterSetName = "DryRun")]
    [switch]$DryRun,

    [Parameter(ParameterSetName = "Apply")]
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$configFullPath = if ([System.IO.Path]::IsPathRooted($ConfigPath)) {
    $ConfigPath
} else {
    Join-Path $workspace $ConfigPath
}

$sessionConfig = $null
if (Test-Path -LiteralPath $configFullPath -PathType Leaf) {
    $sessionConfig = Get-Content -LiteralPath $configFullPath -Raw | ConvertFrom-Json
}

function Resolve-WorkspacePath {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    $expanded = [Environment]::ExpandEnvironmentVariables($PathValue)
    if ([System.IO.Path]::IsPathRooted($expanded)) {
        return $expanded
    }
    return Join-Path $workspace $expanded
}

if (-not $VaultPath) {
    if ($sessionConfig -and $sessionConfig.memory_root) {
        $VaultPath = Resolve-WorkspacePath -PathValue ([string]$sessionConfig.memory_root)
    } else {
        $VaultPath = Join-Path $workspace "_obsidian_vault"
    }
} elseif (-not [System.IO.Path]::IsPathRooted($VaultPath)) {
    $VaultPath = Resolve-WorkspacePath -PathValue $VaultPath
}

$date = Get-Date
$dateString = $date.ToString("yyyy-MM-dd")
$stamp = $date.ToString("yyyy-MM-dd HH:mm")
$dailyDirName = if ($sessionConfig -and $sessionConfig.daily_dir) { [string]$sessionConfig.daily_dir } else { "Daily" }
$currentStateRelPath = if ($sessionConfig -and $sessionConfig.current_state_path) { [string]$sessionConfig.current_state_path } else { "System/Assistant/Shared/Current State.md" }
$dailyDir = Join-Path $VaultPath $dailyDirName
$dailyPath = Join-Path $dailyDir "$dateString.md"
$currentStatePath = Join-Path $VaultPath ($currentStateRelPath -replace '/', [System.IO.Path]::DirectorySeparatorChar)
$sharedDir = Split-Path -Parent $currentStatePath

function Invoke-GitText {
    param([string[]]$Arguments)
    try {
        $output = & git @Arguments 2>$null
        if ($LASTEXITCODE -ne 0) {
            return @()
        }
        return @($output)
    } catch {
        return @()
    }
}

function Convert-ToBulletLines {
    param(
        [string]$Label,
        [string[]]$Items
    )

    $cleanItems = @($Items | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($cleanItems.Count -eq 0) {
        return @()
    }
    $lines = @("- ${Label}:")
    foreach ($item in $cleanItems) {
        $lines += "  - $(([string]$item).Trim())"
    }
    return $lines
}

function Convert-ToConfigRelativePath {
    param([Parameter(Mandatory = $true)][string]$LiteralPath)

    $fullRoot = [System.IO.Path]::GetFullPath($VaultPath).TrimEnd('\', '/')
    $fullPath = [System.IO.Path]::GetFullPath($LiteralPath)
    if (-not $fullPath.StartsWith($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing memory write outside memory root: $fullPath"
    }
    $relative = $fullPath.Substring($fullRoot.Length).TrimStart('\', '/')
    return ($relative -replace '\\', '/')
}

function Test-GlobMatch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,
        [Parameter(Mandatory = $true)]
        [string]$Pattern
    )

    $normalizedPattern = [regex]::Escape(($Pattern -replace '\\', '/'))
    $normalizedPattern = $normalizedPattern -replace '\\\*', '.*'
    $normalizedPattern = $normalizedPattern -replace '\\\?', '.'
    return $Value -match "^$normalizedPattern$"
}

function Assert-SessionMemoryTarget {
    param([Parameter(Mandatory = $true)][string]$LiteralPath)

    $relative = Convert-ToConfigRelativePath -LiteralPath $LiteralPath
    $allowed = if ($sessionConfig -and $sessionConfig.allowed_writes) { @($sessionConfig.allowed_writes) } else { @("Daily/*.md", "System/Assistant/Shared/Current State.md") }
    $forbidden = if ($sessionConfig -and $sessionConfig.forbidden) { @($sessionConfig.forbidden) } else { @(".env", "auth.json", ".obsidian/*", "_hermes/*", ".git/*") }
    foreach ($pattern in $forbidden) {
        if (Test-GlobMatch -Value $relative -Pattern ([string]$pattern)) {
            throw "Refusing forbidden memory target: $relative"
        }
    }
    foreach ($pattern in $allowed) {
        if (Test-GlobMatch -Value $relative -Pattern ([string]$pattern)) {
            return $relative
        }
    }
    throw "Refusing non-allowlisted memory target: $relative"
}

$dailyRelative = Assert-SessionMemoryTarget -LiteralPath $dailyPath
$currentStateRelative = Assert-SessionMemoryTarget -LiteralPath $currentStatePath

$gitStatus = Invoke-GitText -Arguments @("status", "--porcelain=v1")
$recentCommit = (Invoke-GitText -Arguments @("log", "-1", "--date=iso", "--pretty=format:%h %ad %s")) -join "`n"
$changedTracked = @($gitStatus | Where-Object { $_ -match '^\s*[MADRCU]{1,2}\s+' })
$untracked = @($gitStatus | Where-Object { $_ -match '^\?\?\s+' })

if ([string]::IsNullOrWhiteSpace($Summary)) {
    $Summary = "Closed session memory checkpoint for Hermes Guild workspace."
}
if ($NextAction.Count -eq 0) {
    $NextAction = @(
        "Review dry-run memory candidate before applying.",
        "Keep path/cache cleanup dry-run until explicit approval."
    )
}
if ($Risk.Count -eq 0) {
    $Risk = @(
        "Working tree is dirty; do not revert unrelated user changes.",
        "Do not treat _obsidian_vault as cache because it is a junction to the real vault."
    )
}

$candidateLines = @(
    "",
    "## $stamp Session Close - $Source",
    "",
    "- Summary: $($Summary.Trim())",
    "- Workspace: $workspace",
    "- Last commit: $recentCommit",
    "- Git dirty entries: $($gitStatus.Count)",
    "- Tracked changed/deleted entries: $($changedTracked.Count)",
    "- Untracked entries: $($untracked.Count)"
)
$candidateLines += Convert-ToBulletLines -Label "Next action" -Items $NextAction
$candidateLines += Convert-ToBulletLines -Label "Risk" -Items $Risk
$candidateLines += @(
    "",
    "### Changed Paths Snapshot",
    ""
)
if ($gitStatus.Count -eq 0) {
    $candidateLines += "- Working tree clean."
} else {
    foreach ($line in ($gitStatus | Select-Object -First 40)) {
        $candidateLines += ("- {0}" -f $line)
    }
    if ($gitStatus.Count -gt 40) {
        [int]$omittedCount = [int]$gitStatus.Count
        $omittedCount = $omittedCount - 40
        $candidateLines += ('- ... {0} more entries omitted.' -f $omittedCount)
    }
}
$candidateLines += ""

$currentState = @(
    "# Current State",
    "",
    "Updated: $stamp",
    "Source: $Source",
    "",
    "## Active Focus",
    "",
    "- $($Summary.Trim())",
    "",
    "## Next Actions"
)
foreach ($item in $NextAction) {
    $currentState += "- $item"
}
$currentState += @(
    "",
    "## Guardrails"
)
foreach ($item in $Risk) {
    $currentState += "- $item"
}
$currentState += @(
    "",
    "## Workspace Snapshot",
    "",
    "- Workspace: $workspace",
    "- Last commit: $recentCommit",
    "- Git dirty entries: $($gitStatus.Count)",
    "- Daily note: $dailyRelative"
)

if (-not $Apply) {
    [pscustomobject]@{
        ok = $true
        mode = "dry_run"
        config = $configFullPath
        memory_root = $VaultPath
        would_append_daily = $dailyPath
        would_write_current_state = $currentStatePath
        allowlisted_targets = @($dailyRelative, $currentStateRelative)
        candidate = ($candidateLines -join "`n")
        current_state = ($currentState -join "`n")
    }
    exit 0
}

New-Item -ItemType Directory -Force -Path $dailyDir | Out-Null
New-Item -ItemType Directory -Force -Path $sharedDir | Out-Null

if (-not (Test-Path -LiteralPath $dailyPath)) {
    @(
        "# $dateString",
        "",
        "## Log",
        ""
    ) | Set-Content -LiteralPath $dailyPath -Encoding UTF8
}

Add-Content -LiteralPath $dailyPath -Value ($candidateLines -join "`n") -Encoding UTF8
Set-Content -LiteralPath $currentStatePath -Value ($currentState -join "`n") -Encoding UTF8

[pscustomobject]@{
    ok = $true
    mode = "apply"
    config = $configFullPath
    daily = $dailyPath
    current_state = $currentStatePath
    allowlisted_targets = @($dailyRelative, $currentStateRelative)
    git_dirty_entries = $gitStatus.Count
}
