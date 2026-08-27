param(
  [Parameter(Mandatory = $true)]
  [string]$Device
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot

& (Join-Path $PSScriptRoot "apply-esphome-speaker-race-fix.ps1")
& (Join-Path $PSScriptRoot "build-dashboard-bundle.ps1")
& (Join-Path $projectDir ".venv/Scripts/python.exe") -m esphome run (Join-Path $projectDir "device.yaml") --device $Device
