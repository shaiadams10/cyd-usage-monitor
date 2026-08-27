param(
    [string]$LegacyHeader = "..\esp32s3-home-assistant-legacy-2026-08-22\include\secrets.h",
    [string]$Destination = ".\secrets.yaml"
)

$ErrorActionPreference = "Stop"

function Get-CStringDefine {
    param([string]$Text, [string]$Name)

    $pattern = '(?m)^\s*#define\s+' + [regex]::Escape($Name) + '\s+"((?:\\.|[^"\\])*)"\s*$'
    $match = [regex]::Match($Text, $pattern)
    if (-not $match.Success) {
        throw "Missing $Name in $LegacyHeader"
    }
    return [regex]::Unescape($match.Groups[1].Value)
}

function ConvertTo-YamlSingleQuoted {
    param([string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

$resolvedLegacy = (Resolve-Path -LiteralPath $LegacyHeader).Path
$resolvedDestination = [System.IO.Path]::GetFullPath($Destination)
$legacyText = [System.IO.File]::ReadAllText($resolvedLegacy)
$wifiSsid = Get-CStringDefine -Text $legacyText -Name "WIFI_SSID"
$wifiPassword = Get-CStringDefine -Text $legacyText -Name "WIFI_PASSWORD"

if ($wifiSsid -eq "YOUR_WIFI_SSID" -or $wifiPassword -eq "YOUR_WIFI_PASSWORD") {
    throw "The legacy header still contains placeholder Wi-Fi values."
}

$apiBytes = [byte[]]::new(32)
[System.Security.Cryptography.RandomNumberGenerator]::Fill($apiBytes)
$apiKey = [Convert]::ToBase64String($apiBytes)

$otaBytes = [byte[]]::new(24)
[System.Security.Cryptography.RandomNumberGenerator]::Fill($otaBytes)
$otaPassword = [Convert]::ToBase64String($otaBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')

$yaml = @(
    "# Generated locally from the ignored legacy configuration. Do not commit."
    "wifi_ssid: $(ConvertTo-YamlSingleQuoted $wifiSsid)"
    "wifi_password: $(ConvertTo-YamlSingleQuoted $wifiPassword)"
    "api_encryption_key: $(ConvertTo-YamlSingleQuoted $apiKey)"
    "ota_password: $(ConvertTo-YamlSingleQuoted $otaPassword)"
) -join [Environment]::NewLine

[System.IO.File]::WriteAllText($resolvedDestination, $yaml + [Environment]::NewLine)
Write-Host "Migrated Wi-Fi configuration and generated fresh API/OTA credentials without displaying secret values."

