param(
    [string[]]$Pattern = @(),

    [string[]]$Name = @(),

    [int[]]$ProcessId = @(),

    [int]$Limit = 50,

    [switch]$IncludeChildren,

    [switch]$LeafOnly,

    [switch]$Stop,

    [switch]$DryRun,

    [switch]$AllowMultiple,

    [switch]$AllowHermes,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Write-Result {
    param([Parameter(Mandatory = $true)][object]$Value)

    if ($Json) {
        $Value | ConvertTo-Json -Depth 8
        return
    }
    $Value
}

function Stop-WithResult {
    param(
        [Parameter(Mandatory = $true)][string]$Reason,
        [int]$ExitCode = 1
    )

    if ($Json) {
        Write-Result ([pscustomobject]@{
            ok = $false
            action = if ($Stop) { "stop" } else { "inspect" }
            blocked_reason = $Reason
        })
        exit $ExitCode
    }

    throw $Reason
}

function Convert-ProcessRow {
    param([Parameter(Mandatory = $true)]$Process)

    $created = $null
    if ($Process.CreationDate) {
        if ($Process.CreationDate -is [datetime]) {
            $created = $Process.CreationDate.ToString("s")
        } else {
            try {
                $created = ([Management.ManagementDateTimeConverter]::ToDateTime([string]$Process.CreationDate)).ToString("s")
            } catch {
                $created = [string]$Process.CreationDate
            }
        }
    }

    [pscustomobject]@{
        pid = [int]$Process.ProcessId
        parent_pid = [int]$Process.ParentProcessId
        name = [string]$Process.Name
        created = $created
        command_line = [string]$Process.CommandLine
    }
}

function Test-ProtectedProcess {
    param([Parameter(Mandatory = $true)]$Process)

    $commandLine = [string]$Process.CommandLine
    $name = [string]$Process.Name

    if ($Process.ProcessId -eq $PID) {
        return "current_shell"
    }
    if ($commandLine -match "hermes_cli\.main gateway run") {
        return "hermes_gateway"
    }
    if ($commandLine -match "hermes-agent|\\hermes\\|invoke-hermes|send-telegram-home") {
        return "hermes_runtime"
    }
    if ($commandLine -match "codex|opencode") {
        return "agent_runtime"
    }
    if ($name -in @("System", "Registry", "Idle")) {
        return "system_process"
    }
    return $null
}

function Get-Descendants {
    param(
        [Parameter(Mandatory = $true)]$AllProcesses,
        [Parameter(Mandatory = $true)][int[]]$ParentIds
    )

    $seen = @{}
    $queue = [System.Collections.Generic.Queue[int]]::new()
    foreach ($id in $ParentIds) {
        $queue.Enqueue($id)
    }

    while ($queue.Count -gt 0) {
        $parent = $queue.Dequeue()
        foreach ($child in @($AllProcesses | Where-Object { $_.ParentProcessId -eq $parent })) {
            if (-not $seen.ContainsKey($child.ProcessId)) {
                $seen[$child.ProcessId] = $child
                $queue.Enqueue([int]$child.ProcessId)
            }
        }
    }

    @($seen.Values)
}

if ($Limit -lt 1) {
    Stop-WithResult -Reason "limit_must_be_at_least_1" -ExitCode 1
}

if (-not $ProcessId -and -not $Pattern -and -not $Name) {
    Stop-WithResult -Reason "query_required_refusing_broad_process_listing" -ExitCode 1
}

$all = @(Get-CimInstance Win32_Process)
$matches = @()

if ($ProcessId) {
    $pidSet = @{}
    foreach ($id in $ProcessId) {
        $pidSet[[int]$id] = $true
    }
    $matches += @($all | Where-Object { $pidSet.ContainsKey([int]$_.ProcessId) })
}

foreach ($item in $Name) {
    if ([string]::IsNullOrWhiteSpace($item)) {
        continue
    }
    $matches += @($all | Where-Object { $_.Name -ieq $item -or $_.Name -ieq "$item.exe" })
}

foreach ($item in $Pattern) {
    if ([string]::IsNullOrWhiteSpace($item) -or $item.Trim().Length -lt 3) {
        Stop-WithResult -Reason "pattern_must_be_at_least_3_characters" -ExitCode 1
    }
    $needle = $item.Trim()
    $matches += @($all | Where-Object {
        ([string]$_.CommandLine) -like "*$needle*" -or ([string]$_.Name) -like "*$needle*"
    })
}

$unique = [ordered]@{}
foreach ($process in $matches) {
    if ($process.ProcessId -ne $PID -and ([string]$process.CommandLine) -notmatch "find-process\.ps1") {
        $unique[[string]$process.ProcessId] = $process
    }
}

$selected = @($unique.Values)

if ($IncludeChildren -and $selected) {
    foreach ($child in Get-Descendants -AllProcesses $all -ParentIds @($selected | ForEach-Object { [int]$_.ProcessId })) {
        if ($child.ProcessId -ne $PID -and ([string]$child.CommandLine) -notmatch "find-process\.ps1") {
            $unique[[string]$child.ProcessId] = $child
        }
    }
    $selected = @($unique.Values)
}

if ($LeafOnly -and $selected) {
    $selected = @($selected | Where-Object {
        $candidate = $_
        -not @($selected | Where-Object { $_.ParentProcessId -eq $candidate.ProcessId })
    })
}

$selected = @($selected | Sort-Object CreationDate, ProcessId | Select-Object -First $Limit)
$rows = @($selected | ForEach-Object { Convert-ProcessRow $_ })

if (-not $Stop) {
    Write-Result ([pscustomobject]@{
        ok = $true
        action = "inspect"
        count = $rows.Count
        processes = $rows
    })
    exit 0
}

if (-not $selected) {
    Write-Result ([pscustomobject]@{
        ok = $false
        action = "stop"
        stopped = @()
        blocked_reason = "no_matching_process"
    })
    exit 2
}

if ($selected.Count -gt 1 -and -not $AllowMultiple) {
    Write-Result ([pscustomobject]@{
        ok = $false
        action = "stop"
        candidates = $rows
        blocked_reason = "multiple_matches_require_allow_multiple"
    })
    exit 3
}

$blocked = @()
foreach ($process in $selected) {
    $reason = Test-ProtectedProcess -Process $process
    if ($reason -and -not $AllowHermes) {
        $blocked += [pscustomobject]@{
            pid = [int]$process.ProcessId
            name = [string]$process.Name
            reason = $reason
            command_line = [string]$process.CommandLine
        }
    }
}

if ($blocked) {
    Write-Result ([pscustomobject]@{
        ok = $false
        action = "stop"
        candidates = $rows
        blocked = $blocked
        blocked_reason = "protected_process_requires_allow_hermes"
    })
    exit 4
}

if ($DryRun) {
    Write-Result ([pscustomobject]@{
        ok = $true
        action = "stop"
        dry_run = $true
        would_stop = $rows
    })
    exit 0
}

$stopped = @()
foreach ($process in $selected) {
    Stop-Process -Id $process.ProcessId -Force
    $stopped += Convert-ProcessRow $process
}

Write-Result ([pscustomobject]@{
    ok = $true
    action = "stop"
    stopped = $stopped
})
