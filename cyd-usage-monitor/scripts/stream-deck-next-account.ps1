[CmdletBinding()]
param(
    [string]$ProfileId,
    [switch]$ListAccounts
)

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

function Get-PrivateApiOrigin([string]$Endpoint) {
    if ($Endpoint -cnotmatch '^http://((?:0|[1-9][0-9]{0,2})(?:\.(?:0|[1-9][0-9]{0,2})){3})(?::([0-9]{1,5}))?/api/v1/next-account$') {
        throw "Invalid private device endpoint."
    }
    $octets = @($Matches[1].Split('.') | ForEach-Object { [int]$_ })
    if (($octets | Where-Object { $_ -gt 255 }).Count -gt 0 -or
        ($Matches[2] -and ([int]$Matches[2] -lt 1 -or [int]$Matches[2] -gt 65535)) -or
        -not ($octets[0] -eq 10 -or ($octets[0] -eq 172 -and $octets[1] -ge 16 -and $octets[1] -le 31) -or
              ($octets[0] -eq 192 -and $octets[1] -eq 168))) {
        throw "Invalid private device endpoint."
    }
    return ([Uri]$Endpoint).GetLeftPart([UriPartial]::Authority)
}

function Invoke-PrivateApi([string]$Url, [string]$Token, [string]$Body = '') {
    if ([string]::IsNullOrWhiteSpace($Token) -or $Token.Contains("`r") -or $Token.Contains("`n")) {
        throw "Invalid device token configuration."
    }
    try {
        $request = New-Object -ComObject WinHttp.WinHttpRequest.5.1
        $request.SetProxy(1) # HTTPREQUEST_PROXYSETTING_DIRECT
        $request.Option(6) = $false # WinHttpRequestOption_EnableRedirects
        $request.SetTimeouts(500, 1000, 1000, 2000)
        $method = if ($Body) { 'POST' } else { 'GET' }
        $request.Open($method, $Url, $false)
        $request.SetAutoLogonPolicy(2) # Never send Windows credentials.
        $request.SetRequestHeader('Authorization', "Bearer $Token")
        if ($Body) {
            $request.SetRequestHeader('Content-Type', 'application/json')
            $request.Send($Body)
        } else { $request.Send() }
        if ($request.Status -ne 200) { throw 'Request rejected.' }
        return ($request.ResponseText | ConvertFrom-Json)
    } catch {
        throw "Private device request failed; check the endpoint, token, and server."
    }
}

$endpoint = Get-PrivateUserSetting -Name "CYD_USAGE_MONITOR_NEXT_ACCOUNT_URL"
$token = Get-PrivateUserSetting -Name "CYD_API_TOKEN"
$origin = Get-PrivateApiOrigin $endpoint
if ($ListAccounts -and $ProfileId) { throw "Use either -ListAccounts or -ProfileId." }
if ($ProfileId -and $ProfileId -cnotmatch '^(codex|antigravity)-[a-f0-9]{10}$') {
    throw "Invalid profile ID."
}
if ($ListAccounts) {
    $result = Invoke-PrivateApi "$origin/api/v1/accounts" $token
    $result.accounts | Select-Object id, label, provider, enabled, active
    return
}
if ($ProfileId) {
    $body = @{ profile_id = $ProfileId } | ConvertTo-Json -Compress
    $result = Invoke-PrivateApi "$origin/api/v1/select-account" $token $body
    if ($result.status -ne "ok" -or $result.profile_id -ne $ProfileId) {
        throw "The monitor did not confirm the selected profile."
    }
    Write-Output "CYD usage account selected."
    return
}
$response = Invoke-PrivateApi $endpoint $token
if ([string]::IsNullOrWhiteSpace([string]$response.account_name)) {
    throw "The monitor accepted the request but did not return an account."
}
Write-Output "CYD usage account advanced."
