param(
    [Parameter(Mandatory = $true)]
    [string]$Text,

    [string]$HermesHome = "$env:LOCALAPPDATA\hermes",

    [ValidateRange(1, 60)]
    [int]$TimeoutSec = 20,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$envPath = Join-Path $HermesHome '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Hermes .env not found."
}

$vars = @{}
foreach ($line in Get-Content -LiteralPath $envPath) {
    if ($line -match '^\s*#' -or $line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$') {
        continue
    }

    $key = $Matches[1]
    $value = $Matches[2].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    $vars[$key] = $value
}

$token = $vars['TELEGRAM_BOT_TOKEN']
$chatId = $vars['TELEGRAM_HOME_CHANNEL']

if ([string]::IsNullOrWhiteSpace($token) -or [string]::IsNullOrWhiteSpace($chatId)) {
    throw "Telegram token or home channel is missing from Hermes .env."
}

if ($DryRun) {
    [pscustomobject]@{
        ok = $true
        dry_run = $true
        chat_id_present = $true
        token_present = $true
        text_length = $Text.Length
    } | ConvertTo-Json -Compress
    exit 0
}

$uri = "https://api.telegram.org/bot$token/sendMessage"
$body = @{
    chat_id = $chatId
    text = $Text
}

$response = Invoke-RestMethod -Method Post -Uri $uri -Body $body -TimeoutSec $TimeoutSec
if (-not $response.ok) {
    throw "Telegram sendMessage returned ok=false."
}

[pscustomobject]@{
    ok = $true
    message_id = $response.result.message_id
} | ConvertTo-Json -Compress
