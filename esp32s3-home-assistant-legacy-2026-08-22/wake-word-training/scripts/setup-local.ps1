[CmdletBinding()]
param(
    [string]$Distro = "Ubuntu-22.04"
)

$ErrorActionPreference = "Stop"
$localDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..\local")).Path
$wslLocalDirectory = (& wsl -d $Distro -- wslpath -a $localDirectory).Trim()
if ($LASTEXITCODE -ne 0 -or -not $wslLocalDirectory) {
    throw "Could not translate the training directory into a WSL path."
}

Write-Host "Preparing the local WSL/CUDA training environment..." -ForegroundColor Cyan
& wsl -d $Distro -- bash "$wslLocalDirectory/setup.sh"
if ($LASTEXITCODE -ne 0) {
    throw "Local training setup failed with exit code $LASTEXITCODE."
}

