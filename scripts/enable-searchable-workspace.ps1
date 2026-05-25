[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$WorkspacePath = (Get-Location).Path,

    [string]$HermesHome = "$env:LOCALAPPDATA\hermes",

    [switch]$InstallMissing,

    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'

$WorkspacePath = (Resolve-Path -LiteralPath $WorkspacePath).Path
$runtimeDir = Join-Path $WorkspacePath '_runtime\searchable-workspace'
$manifestPath = Join-Path $runtimeDir 'manifest.json'

$requiredTools = @(
    [pscustomobject]@{
        name = 'es'
        purpose = 'Everything CLI path search'
        install = 'winget install voidtools.Everything.Cli'
    },
    [pscustomobject]@{
        name = 'fd'
        purpose = 'fast scoped filename fallback'
        install = 'scoop install fd'
    },
    [pscustomobject]@{
        name = 'rg'
        purpose = 'fast scoped content search'
        install = 'scoop install ripgrep'
    },
    [pscustomobject]@{
        name = 'bat'
        purpose = 'bounded file preview'
        install = 'scoop install bat'
    },
    [pscustomobject]@{
        name = 'eza'
        purpose = 'small top-level listings'
        install = 'scoop install eza'
    },
    [pscustomobject]@{
        name = 'zoxide'
        purpose = 'human shell navigation only'
        install = 'scoop install zoxide'
    }
)

function Get-ToolStatus {
    param([Parameter(Mandatory = $true)][object]$Tool)

    $cmd = Get-Command $Tool.name -ErrorAction SilentlyContinue
    [pscustomobject]@{
        name = $Tool.name
        purpose = $Tool.purpose
        available = [bool]$cmd
        path = if ($cmd) { $cmd.Source } else { $null }
        install_hint = $Tool.install
    }
}

$tools = @($requiredTools | ForEach-Object { Get-ToolStatus -Tool $_ })
$missing = @($tools | Where-Object { -not $_.available })

if ($InstallMissing -and $missing.Count -gt 0) {
    foreach ($tool in $missing) {
        $parts = $tool.install_hint -split '\s+'
        $exe = $parts[0]
        $args = @($parts | Select-Object -Skip 1)

        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
            Write-Warning "Installer not available for $($tool.name): $exe"
            continue
        }

        if ($PSCmdlet.ShouldProcess($tool.name, $tool.install_hint)) {
            & $exe @args
        }
    }

    $tools = @($requiredTools | ForEach-Object { Get-ToolStatus -Tool $_ })
    $missing = @($tools | Where-Object { -not $_.available })
}

$routes = [ordered]@{
    find_paths = [ordered]@{
        script = Join-Path $WorkspacePath 'scripts\search-files.ps1'
        order = @('Everything ES', 'fd scoped to root', 'scoped PowerShell fallback')
    }
    search_text = [ordered]@{
        script = Join-Path $WorkspacePath 'scripts\search-content.ps1'
        order = @('rg scoped to path', 'scoped PowerShell fallback')
    }
    preview_file = [ordered]@{
        script = Join-Path $WorkspacePath 'scripts\preview-file.ps1'
        order = @('bat', 'Get-Content bounded fallback')
    }
    inspect_workspace = [ordered]@{
        script = Join-Path $WorkspacePath 'scripts\inspect-workspace.ps1'
        order = @('eza top-level listing', 'Get-ChildItem top-level fallback')
    }
    navigation = [ordered]@{
        rule = 'zoxide is human shell state only; agents must not depend on it for automation'
    }
}

$manifest = [ordered]@{
    schema_version = 'searchable_workspace_v0'
    generated_at = (Get-Date).ToString('o')
    workspace_path = $WorkspacePath
    hermes_home = $HermesHome
    tools = $tools
    missing_tools = @($missing | Select-Object -ExpandProperty name)
    routes = $routes
    guardrails = @(
        'Do not run plain es without query and limit.',
        'Do not run broad recursive Get-ChildItem or Select-String when a route script exists.',
        'Use candidate path lists first, then preview selected files.',
        'Keep zoxide for human navigation only.'
    )
}

if (-not $CheckOnly) {
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    [System.Environment]::SetEnvironmentVariable('HERMES_SEARCHABLE_WORKSPACE', $manifestPath, [System.EnvironmentVariableTarget]::User)
}

$manifest | ConvertTo-Json -Depth 8
