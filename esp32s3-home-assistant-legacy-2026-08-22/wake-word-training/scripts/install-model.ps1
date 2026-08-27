[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [Parameter(Mandatory = $true)]
    [string]$ModelPath,

    [Parameter(Mandatory = $true)]
    [string]$OpenWakeWordSharePath,

    [switch]$Force
)

$ErrorActionPreference = "Stop"
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$validator = Join-Path $scriptDirectory "validate-model.ps1"
$validation = & $validator -ModelPath $ModelPath
$source = Get-Item -LiteralPath $validation.File
$resolvedShare = Resolve-Path -LiteralPath $OpenWakeWordSharePath -ErrorAction Stop
$share = Get-Item -LiteralPath $resolvedShare.Path

if (-not $share.PSIsContainer) {
    throw "OpenWakeWordSharePath must be an existing directory mapped to Home Assistant /share/openwakeword."
}

$destination = Join-Path $share.FullName "hey_burden.tflite"
if ((Test-Path -LiteralPath $destination) -and -not $Force) {
    throw "Destination already exists. Re-run with -Force only after confirming the replacement: $destination"
}

if ($PSCmdlet.ShouldProcess($destination, "Install validated wake-word model")) {
    Copy-Item -LiteralPath $source.FullName -Destination $destination -Force:$Force
    $installedHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
    if ($installedHash -cne $validation.SHA256) {
        throw "Installed model hash does not match the source."
    }

    [pscustomobject]@{
        Installed = $true
        Destination = $destination
        SHA256 = $installedHash
        NextStep = "Restart the openWakeWord app, then reload the Wyoming integration."
    }
}

