[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Query,

    [string]$Root = '.',

    [ValidateRange(1, 1000)]
    [int]$Limit = 20,

    [switch]$Json,

    [switch]$AllowBroad
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Query)) {
    throw 'Query is required. Refusing to run plain Everything ES or broad fallback without a query.'
}

$resolvedRoot = Resolve-Path -LiteralPath $Root -ErrorAction Stop
$rootPath = $resolvedRoot.ProviderPath.TrimEnd('\')
$homePath = (Resolve-Path -LiteralPath $HOME).ProviderPath.TrimEnd('\')
$rootInfo = Get-Item -LiteralPath $rootPath -Force

$isDriveRoot = ($rootPath -match '^[A-Za-z]:$')
if (-not $AllowBroad -and ($isDriveRoot -or $rootPath -ieq $homePath)) {
    throw "Refusing broad file discovery in '$rootPath'. Pass a smaller -Root or use -AllowBroad explicitly."
}

function Convert-SearchResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Source
    )

    [pscustomobject]@{
        path = $Path
        source = $Source
    }
}

function Write-Results {
    param([object[]]$Items)

    $limited = @($Items | Select-Object -First $Limit)
    if ($Json) {
        $limited | ConvertTo-Json -Depth 3
    } else {
        $limited | ForEach-Object { $_.path }
    }
}

function Get-QueryTerms {
    param([string]$Text)

    $Text -split '\s+' |
        Where-Object { $_ -and $_ -notmatch '^(ext|path|parent|parent-path):' } |
        ForEach-Object { $_.Trim('"', "'") } |
        Where-Object { $_.Length -gt 0 }
}

# Option 1: Everything ES. Fastest when Everything is running and IPC is available.
$es = Get-Command es -ErrorAction SilentlyContinue
if ($es) {
    try {
        $esArgs = @('-n', $Limit, '-path', $rootPath)
        if ($Json) {
            $esArgs += '-json'
        }
        $esArgs += $Query

        $output = & $es.Source @esArgs 2>&1
        if ($LASTEXITCODE -eq 0 -and $output) {
            if ($Json) {
                try {
                    $parsed = $output | ConvertFrom-Json
                    $items = @($parsed | ForEach-Object {
                        $path = if ($_.filename) { $_.filename } elseif ($_.path) { $_.path } else { [string]$_ }
                        Convert-SearchResult -Path $path -Source 'everything'
                    })
                    Write-Results -Items $items
                } catch {
                    $output
                }
            } else {
                $output | Select-Object -First $Limit
            }
            exit 0
        }
    } catch {
        # Fall through to option 2. ES often fails when Everything IPC is not running.
    }
}

# Option 2: fd scoped to the chosen root.
$terms = @(Get-QueryTerms -Text $Query)
$primary = if ($terms.Count -gt 0) { [regex]::Escape($terms[0]) } else { '.' }
$fd = Get-Command fd -ErrorAction SilentlyContinue
if ($fd) {
    $fdArgs = @(
        '--hidden',
        '--full-path',
        '--exclude', '.git',
        '--exclude', 'node_modules',
        '--exclude', 'dist',
        '--exclude', 'build',
        '--exclude', 'target',
        '--exclude', '__pycache__',
        '--max-results', ([Math]::Max($Limit * 5, $Limit)),
        $primary,
        $rootPath
    )

    $paths = @(& $fd.Source @fdArgs 2>$null)
    $filtered = $paths | Where-Object {
        $candidate = $_
        foreach ($term in $terms) {
            if ($candidate -notlike "*$term*") {
                return $false
            }
        }
        return $true
    } | ForEach-Object { Convert-SearchResult -Path $_ -Source 'fd' }

    if ($filtered) {
        Write-Results -Items $filtered
        exit 0
    }
}

# Option 3: scoped PowerShell fallback. This is slower, so keep it bounded.
$items = Get-ChildItem -LiteralPath $rootPath -Force -Recurse -ErrorAction SilentlyContinue |
    Where-Object {
        $full = $_.FullName
        if ($full -match '\\(\.git|node_modules|dist|build|target|__pycache__)(\\|$)') {
            return $false
        }
        foreach ($term in $terms) {
            if ($full -notlike "*$term*") {
                return $false
            }
        }
        return $true
    } |
    Select-Object -First $Limit |
    ForEach-Object { Convert-SearchResult -Path $_.FullName -Source 'powershell' }

Write-Results -Items @($items)
