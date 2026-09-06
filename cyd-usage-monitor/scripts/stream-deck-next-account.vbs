Option Explicit
On Error Resume Next

Dim shell, endpoint, token, profileId, request, body, origin, pattern
Set shell = CreateObject("WScript.Shell")
If WScript.Arguments.Count > 1 Then WScript.Quit 2
profileId = ""
If WScript.Arguments.Count = 1 Then
    profileId = WScript.Arguments(0)
    If Not Matches(profileId, "^(codex|antigravity)-[a-f0-9]{10}$") Then WScript.Quit 2
End If
endpoint = PrivateSetting("CYD_USAGE_MONITOR_NEXT_ACCOUNT_URL")
token = PrivateSetting("CYD_API_TOKEN")
If Len(endpoint) = 0 Or Len(Trim(token)) = 0 Then WScript.Quit 2
If InStr(token, vbCr) > 0 Or InStr(token, vbLf) > 0 Then WScript.Quit 2
If Not Matches(endpoint, "^http://[0-9.]+(:[0-9]+)?/api/v1/next-account$") Then WScript.Quit 2
Dim authority, host, octets, i
origin = Left(endpoint, InStr(8, endpoint, "/") - 1)
authority = Mid(origin, 8)
host = Split(authority, ":")(0)
octets = Split(host, ".")
If UBound(octets) <> 3 Then WScript.Quit 2
For i = 0 To 3
    If Len(octets(i)) = 0 Or Len(octets(i)) > 3 Then WScript.Quit 2
    If CInt(octets(i)) > 255 Then WScript.Quit 2
    If Len(octets(i)) > 1 And Left(octets(i), 1) = "0" Then WScript.Quit 2
Next
If Not (CInt(octets(0)) = 10 Or (CInt(octets(0)) = 172 And CInt(octets(1)) >= 16 And CInt(octets(1)) <= 31) Or (CInt(octets(0)) = 192 And CInt(octets(1)) = 168)) Then WScript.Quit 2
If InStr(authority, ":") > 0 Then
    Dim portText
    portText = Split(authority, ":")(1)
    If Len(portText) > 5 Then WScript.Quit 2
    If CLng(portText) < 1 Or CLng(portText) > 65535 Then WScript.Quit 2
End If
If Err.Number <> 0 Then WScript.Quit 2

Set request = CreateObject("WinHttp.WinHttpRequest.5.1")
request.SetProxy 1
request.Option(6) = False
request.setTimeouts 500, 1000, 1000, 2000
If Len(profileId) > 0 Then
    request.open "POST", origin & "/api/v1/select-account", False
Else
    request.open "GET", endpoint, False
End If
request.SetAutoLogonPolicy 2
If Err.Number <> 0 Then WScript.Quit 2
request.setRequestHeader "Authorization", "Bearer " & token
If Len(profileId) > 0 Then
    request.setRequestHeader "Content-Type", "application/json"
    body = "{""profile_id"":""" & profileId & """}"
    request.send body
Else
    request.send
End If
If Err.Number <> 0 Then WScript.Quit 1
If request.status <> 200 Then WScript.Quit 1
If Len(profileId) > 0 Then
    If Not Matches(request.responseText, """status""\s*:\s*""ok""") Then WScript.Quit 1
    If Not Matches(request.responseText, """profile_id""\s*:\s*""" & profileId & """") Then WScript.Quit 1
Else
    If Not Matches(request.responseText, """account_name""\s*:\s*""[^""]+") Then WScript.Quit 1
End If
WScript.Quit 0

Function PrivateSetting(name)
    Dim value
    value = shell.Environment("USER")(name)
    If Len(Trim(value)) = 0 Then value = shell.Environment("PROCESS")(name)
    PrivateSetting = value
End Function

Function Matches(value, expression)
    Dim regex
    Set regex = New RegExp
    regex.Pattern = expression
    Matches = regex.Test(value)
End Function
' No retries: repeating a cycle after an uncertain response could skip an account.
' No credentials, URLs, or responses are printed or passed to another process.
' PowerShell remains available separately for account discovery and diagnostics.
