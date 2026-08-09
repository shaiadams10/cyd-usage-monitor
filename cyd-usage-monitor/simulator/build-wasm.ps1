$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$expectedEmscripten = '3.1.74'
$emsdkRoot = if ($env:EMSDK_ROOT) { $env:EMSDK_ROOT } else { Join-Path $env:USERPROFILE '.tools\emsdk' }
$emsdk = Join-Path $emsdkRoot 'upstream\emscripten\emcc.bat'
$lvgl = Join-Path $projectRoot '.pio\libdeps\esp32-2432S028R\lvgl'
$output = Join-Path $projectRoot 'server\static\lvgl'

function Get-ProjectRelativePath([string]$path) {
  # System.IO.Path.GetRelativePath is unavailable in Windows PowerShell 5.1,
  # which remains common on firmware workstations. URI relative paths work on
  # both Windows PowerShell and modern pwsh runners.
  $rootPath = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  $rootUri = [Uri]$rootPath
  $pathUri = [Uri][System.IO.Path]::GetFullPath($path)
  return [Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString())
}

if (-not (Test-Path $emsdk)) { throw 'Emscripten is missing. Install and activate emsdk first.' }
if (-not (Test-Path $lvgl)) { throw 'PlatformIO LVGL dependency is missing. Run a PlatformIO build first.' }
$version = (& $emsdk --version 2>&1) -join "`n"
if ($version -notmatch [regex]::Escape($expectedEmscripten)) {
  throw "Expected Emscripten $expectedEmscripten, but found: $version"
}
New-Item -ItemType Directory -Force -Path $output | Out-Null

$responseFile = Join-Path $output 'sources.rsp'
$sources = Get-ChildItem -Path (Join-Path $lvgl 'src') -Recurse -Filter *.c |
  ForEach-Object { Get-ProjectRelativePath $_.FullName } |
  Sort-Object |
  ForEach-Object { '"' + $_ + '"' }
$simulatorSource = Get-ProjectRelativePath (Join-Path $PSScriptRoot 'lvgl_cyd_sim.c')
$sources += '"' + $simulatorSource + '"'
Set-Content -Path $responseFile -Value $sources -Encoding utf8
Push-Location $projectRoot
try {
  & $emsdk "@$responseFile" `
    '-I' $PSScriptRoot '-I' (Join-Path $lvgl 'src') '-DLV_CONF_INCLUDE_SIMPLE' `
    "-ffile-prefix-map=$projectRoot=." `
    '-s' 'WASM=1' '-s' 'MODULARIZE=1' '-s' 'EXPORT_NAME=createCydLvgl' '-s' 'ENVIRONMENT=web' `
    '-s' 'EXPORTED_FUNCTIONS=["_cyd_init","_cyd_tick","_cyd_pointer","_cyd_publish_provider_mascots","_cyd_set_codex","_cyd_set_antigravity","_cyd_set_error","_cyd_set_openrouter"]' `
    '-s' 'EXPORTED_RUNTIME_METHODS=["ccall"]' '-s' 'ALLOW_MEMORY_GROWTH=1' '-O3' `
    '-o' (Join-Path $output 'cyd_lvgl.js')
} finally {
  Pop-Location
  Remove-Item -LiteralPath $responseFile -Force
}

# Emscripten emits a whitespace-only line near the wrapper preamble. Normalize
# trailing horizontal whitespace so generated assets pass repository checks
# identically on Windows workstations and GitHub Actions runners.
$generatedJs = Join-Path $output 'cyd_lvgl.js'
$jsText = [System.IO.File]::ReadAllText($generatedJs)
$jsText = [regex]::Replace($jsText, '[ \t]+(?=\r?$)', '', [System.Text.RegularExpressions.RegexOptions]::Multiline)
[System.IO.File]::WriteAllText($generatedJs, $jsText, [System.Text.UTF8Encoding]::new($false))
