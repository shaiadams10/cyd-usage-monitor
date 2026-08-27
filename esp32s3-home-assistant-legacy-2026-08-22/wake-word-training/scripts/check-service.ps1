[CmdletBinding()]
param(
    [string]$HostName = "homeassistant.local",
    [ValidateRange(1, 65535)]
    [int]$Port = 10400,
    [string]$ModelName = "hey_burden",
    [ValidateRange(250, 30000)]
    [int]$TimeoutMilliseconds = 3000,
    [switch]$Detailed
)

$ErrorActionPreference = "Stop"
$client = [System.Net.Sockets.TcpClient]::new()

try {
    $connect = $client.BeginConnect($HostName, $Port, $null, $null)
    if (-not $connect.AsyncWaitHandle.WaitOne($TimeoutMilliseconds)) {
        throw "Timed out connecting to ${HostName}:$Port."
    }
    $client.EndConnect($connect)
    $client.ReceiveTimeout = $TimeoutMilliseconds
    $client.SendTimeout = $TimeoutMilliseconds
    $stream = $client.GetStream()

    $request = '{"type":"describe","data":{}}' + "`n"
    $requestBytes = [System.Text.Encoding]::UTF8.GetBytes($request)
    $stream.Write($requestBytes, 0, $requestBytes.Length)
    $stream.Flush()

    $headerBytes = [System.Collections.Generic.List[byte]]::new()
    while ($true) {
        $value = $stream.ReadByte()
        if ($value -lt 0) { throw "Service closed the connection before sending an event header." }
        if ($value -eq 10) { break }
        $headerBytes.Add([byte]$value)
        if ($headerBytes.Count -gt 65536) { throw "Wyoming event header exceeded 64 KiB." }
    }

    $headerText = [System.Text.Encoding]::UTF8.GetString($headerBytes.ToArray())
    $event = $headerText | ConvertFrom-Json
    $description = $event.data

    if ($event.data_length -and [int]$event.data_length -gt 0) {
        $length = [int]$event.data_length
        $dataBytes = New-Object byte[] $length
        $offset = 0
        while ($offset -lt $length) {
            $read = $stream.Read($dataBytes, $offset, $length - $offset)
            if ($read -le 0) { throw "Service closed the connection during the Wyoming data payload." }
            $offset += $read
        }
        $description = ([System.Text.Encoding]::UTF8.GetString($dataBytes)) | ConvertFrom-Json
    }

    $descriptionJson = $description | ConvertTo-Json -Depth 20 -Compress
    $escapedModel = [regex]::Escape($ModelName)
    $installed = $descriptionJson -match ('"' + $escapedModel + '"')

    $result = [ordered]@{
        Reachable = $true
        Endpoint = "${HostName}:$Port"
        EventType = $event.type
        Model = $ModelName
        ModelInstalled = $installed
    }
    if ($Detailed) { $result.Description = $description }
    [pscustomobject]$result
}
finally {
    $client.Dispose()
}

