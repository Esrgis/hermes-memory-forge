function Resolve-HermesCli {
    [CmdletBinding()]
    param(
        [string]$Workspace
    )

    if ($env:HERMES_CLI -and (Test-Path -LiteralPath $env:HERMES_CLI -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $env:HERMES_CLI).Path
    }

    $command = Get-Command hermes -ErrorAction SilentlyContinue
    if ($command -and $command.Source) {
        return $command.Source
    }

    $localAppData = $env:LOCALAPPDATA
    if ($localAppData) {
        $candidate = Join-Path $localAppData "hermes\hermes-agent\venv\Scripts\hermes.exe"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }

    if ($Workspace) {
        $mapPath = Join-Path $Workspace "HERMES_MAP.md"
        if (Test-Path -LiteralPath $mapPath -PathType Leaf) {
            $line = Get-Content -LiteralPath $mapPath |
                Where-Object { $_ -match 'Hermes CLI:\s*`?([^`]+)`?' } |
                Select-Object -First 1
            if ($line -and $line -match 'Hermes CLI:\s*`?([^`]+)`?') {
                $candidate = $Matches[1].Trim()
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    return $candidate
                }
            }
        }
    }

    throw "Hermes CLI not found. Set HERMES_CLI or check HERMES_MAP.md."
}
