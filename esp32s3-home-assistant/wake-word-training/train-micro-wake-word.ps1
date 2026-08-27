param(
    [ValidateSet("features", "train", "export", "all")]
    [string]$Stage = "all",
    [switch]$Resume,
    [string]$WslDistro = "Ubuntu-22.04",
    [string]$CacheRoot = ""
)

$ErrorActionPreference = "Stop"
$trainerDirectory = (wsl.exe -d $WslDistro -- wslpath -a $PSScriptRoot).Trim()
$wslHome = (wsl.exe -d $WslDistro -- bash -lc 'printf %s "$HOME"').Trim()
$cache = if ($CacheRoot) { $CacheRoot } else { "$wslHome/.cache/hey-burden-training" }
$trainer = "$trainerDirectory/train_micro_wake_word.py"
$artifacts = "$trainerDirectory/artifacts"
$resumeArgument = if ($Resume) { "--resume" } else { "" }

$command = @"
source '$cache/mww-venv/bin/activate'
export LD_LIBRARY_PATH=`$(find '$cache/mww-venv/lib/python3.10/site-packages/nvidia' -type d -name lib | paste -sd: -):`$LD_LIBRARY_PATH
python '$trainer' --stage '$Stage' --artifacts '$artifacts' $resumeArgument
"@

wsl.exe -d $WslDistro -- bash -lc $command
