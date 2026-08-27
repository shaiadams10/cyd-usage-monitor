param(
    [string]$WslDistro = "Ubuntu-22.04",
    [string]$CacheRoot = ""
)

$ErrorActionPreference = "Stop"
$trainerDirectory = (wsl.exe -d $WslDistro -- wslpath -a $PSScriptRoot).Trim()
$wslHome = (wsl.exe -d $WslDistro -- bash -lc 'printf %s "$HOME"').Trim()
$cache = if ($CacheRoot) { $CacheRoot } else { "$wslHome/.cache/hey-burden-training" }
$revision = "4665173cd35f1cff9a61e06fc427f124766c488e"

$command = @"
set -e
if [ ! -d '$cache/src/micro-wake-word/.git' ]; then
  git clone https://github.com/OHF-Voice/micro-wake-word.git '$cache/src/micro-wake-word'
fi
git -C '$cache/src/micro-wake-word' fetch --depth 1 origin '$revision'
git -C '$cache/src/micro-wake-word' checkout --detach '$revision'
if [ ! -x '$cache/mww-venv/bin/python' ]; then
  python3.10 -m venv '$cache/mww-venv'
fi
source '$cache/mww-venv/bin/activate'
python -m pip install --upgrade pip
python -m pip install -r '$trainerDirectory/requirements.txt'
python -m pip install -e '$cache/src/micro-wake-word'
"@

wsl.exe -d $WslDistro -- bash -lc $command
