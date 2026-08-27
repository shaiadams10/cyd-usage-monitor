[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Get-PrivateUserSetting {
    param([Parameter(Mandatory)][string]$Name)

    $value = [Environment]::GetEnvironmentVariable($Name, "User")
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Required environment variable $Name is not configured."
    }
    return $value
}

$endpoint = Get-PrivateUserSetting -Name "CYD_USAGE_MONITOR_NEXT_ACCOUNT_URL"
$token = Get-PrivateUserSetting -Name "CYD_API_TOKEN"

$response = Invoke-RestMethod `
    -Uri $endpoint `
    -Method Get `
    -Headers @{ Authorization = "Bearer $token" } `
    -TimeoutSec 10

if ([string]::IsNullOrWhiteSpace([string]$response.account_name)) {
    throw "The monitor accepted the request but did not return an account."
}

Write-Output "CYD usage account advanced."
