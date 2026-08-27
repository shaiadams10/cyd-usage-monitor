[CmdletBinding()]
param(
    [ValidateSet("prepare", "generate", "augment", "train", "convert", "all")]
    [string]$Stage = "all",
    [string]$Distro = "Ubuntu-22.04"
)

$ErrorActionPreference = "Stop"
$trainingRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$localDirectory = Join-Path $trainingRoot "local"
$artifactDirectory = Join-Path $trainingRoot "artifacts"
$wslLocalDirectory = (& wsl -d $Distro -- wslpath -a $localDirectory).Trim()
$wslArtifactDirectory = (& wsl -d $Distro -- wslpath -a $artifactDirectory).Trim()
if ($LASTEXITCODE -ne 0 -or -not $wslLocalDirectory -or -not $wslArtifactDirectory) {
    throw "Could not translate the training paths into WSL paths."
}

Write-Host "Starting local '$Stage' stage. Progress will remain visible in this terminal." -ForegroundColor Cyan
& wsl -d $Distro -- bash "$wslLocalDirectory/run_training.sh" $wslArtifactDirectory $Stage
if ($LASTEXITCODE -ne 0) {
    throw "Local training stage failed with exit code $LASTEXITCODE."
}
