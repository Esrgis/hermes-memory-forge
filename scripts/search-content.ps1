[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Pattern,

    [string]$Path = '.',

    [ValidateRange(1, 1000)]
    [int]$Limit = 80,

    [string[]]$Glob = @(),

    [switch]$IgnoreCase,

    [switch]$Json,

    [switch]$AllowBroad
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Pattern)) {
    throw 'Pattern is required. Refusing broad content search without a pattern.'
}

$resolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction Stop
$rootPath = $resolvedPath.ProviderPath.TrimEnd('\')
$homePath = (Resolve-Path -LiteralPath $HOME).ProviderPath.TrimEnd('\')
$isDriveRoot = ($rootPath -match '^[A-Za-z]:$')

if (-not $AllowBroad -and ($isDriveRoot -or $rootPath -ieq $homePath)) {
    throw "Refusing broad content search in '$rootPath'. Pass a smaller -Path or use -AllowBroad explicitly."
}

function Write-TextResults {
    param([object[]]$Items)

    $limited = @($Items | Select-Object -First $Limit)
    if ($Json) {
        $limited | ConvertTo-Json -Depth 4
    } else {
        $limited | ForEach-Object {
            if ($_.line) {
                '{0}:{1}:{2}' -f $_.path, $_.line_number, $_.line
            } else {
                '{0}:{1}' -f $_.path, $_.line_number
            }
        }
    }
}

$rg = Get-Command rg -ErrorAction SilentlyContinue
if ($rg) {
    $rgArgs = @(
        '--line-number',
        '--with-filename',
        '--hidden',
        '--max-count', $Limit,
        '--glob', '!.git/**',
        '--glob', '!node_modules/**',
        '--glob', '!dist/**',
        '--glob', '!build/**',
        '--glob', '!target/**',
        '--glob', '!__pycache__/**'
    )

    if ($IgnoreCase) {
        $rgArgs += '--ignore-case'
    }

    foreach ($item in $Glob) {
        $rgArgs += @('--glob', $item)
    }

    if ($Json) {
        $rgArgs += '--json'
    }

    $rgArgs += @('--', $Pattern, $rootPath)
    $output = @(& $rg.Source @rgArgs 2>$null)

    if ($LASTEXITCODE -eq 0 -and $output) {
        if ($Json) {
            $matches = @()
            foreach ($line in $output) {
                try {
                    $event = $line | ConvertFrom-Json
                } catch {
                    continue
                }
                if ($event.type -eq 'match') {
                    $matches += [pscustomobject]@{
                        path        = $event.data.path.text
                        line_number = $event.data.line_number
                        line        = $event.data.lines.text.TrimEnd()
                    }
                }
                if ($matches.Count -ge $Limit) {
                    break
                }
            }
            Write-TextResults -Items $matches
        } else {
            $output | Select-Object -First $Limit
        }
        exit 0
    }

    if ($LASTEXITCODE -eq 1) {
        if ($Json) {
            @() | ConvertTo-Json
        }
        exit 0
    }
}

$filePatterns = if ($Glob.Count -gt 0) { $Glob } else { @('*') }
$matches = foreach ($filePattern in $filePatterns) {
    Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force -ErrorAction SilentlyContinue -Include $filePattern |
        Where-Object { $_.FullName -notmatch '\\(\.git|node_modules|dist|build|target|__pycache__)(\\|$)' } |
        Select-String -Pattern $Pattern -CaseSensitive:(!$IgnoreCase) -ErrorAction SilentlyContinue |
        Select-Object -First $Limit |
        ForEach-Object {
            [pscustomobject]@{
                path        = $_.Path
                line_number = $_.LineNumber
                line        = $_.Line.TrimEnd()
            }
        }
}

Write-TextResults -Items @($matches)
