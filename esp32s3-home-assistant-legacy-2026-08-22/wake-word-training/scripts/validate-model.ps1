[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ModelPath,

    [string]$ExpectedFileName = "hey_burden.tflite"
)

$ErrorActionPreference = "Stop"
$resolvedModel = Resolve-Path -LiteralPath $ModelPath -ErrorAction Stop
$model = Get-Item -LiteralPath $resolvedModel.Path

if ($model.PSIsContainer) {
    throw "ModelPath must identify a file: $($model.FullName)"
}

if ($model.Name -cne $ExpectedFileName) {
    throw "Expected model filename '$ExpectedFileName', received '$($model.Name)'."
}

if ($model.Length -lt 10240 -or $model.Length -gt 100MB) {
    throw "Unexpected model size ($($model.Length) bytes); expected 10 KiB to 100 MiB."
}

$header = New-Object byte[] 8
$stream = [System.IO.File]::OpenRead($model.FullName)
try {
    if ($stream.Read($header, 0, $header.Length) -ne $header.Length) {
        throw "Model is too short to contain a TensorFlow Lite header."
    }
}
finally {
    $stream.Dispose()
}

$identifier = [System.Text.Encoding]::ASCII.GetString($header, 4, 4)
if ($identifier -cne "TFL3") {
    throw "The file does not have the TensorFlow Lite TFL3 FlatBuffer identifier."
}

$hash = Get-FileHash -LiteralPath $model.FullName -Algorithm SHA256
[pscustomobject]@{
    Valid = $true
    File = $model.FullName
    Bytes = $model.Length
    SHA256 = $hash.Hash
}

