# export-artifacts.ps1
# Generates all PCB, schematic, Gerber, KiCad, and 3D manufacturing artifacts using tscircuit

$ErrorActionPreference = "Stop"

$CircuitDir = Split-Path -Parent $PSScriptRoot
Set-Location $CircuitDir
$Tsci = Join-Path $CircuitDir "node_modules\.bin\tsci.cmd"

if (!(Test-Path $Tsci)) {
    throw "Project-local tscircuit CLI is missing. Run 'npm install' in $CircuitDir first."
}

$DistDir = Join-Path $CircuitDir "dist"
if (!(Test-Path $DistDir)) {
    New-Item -ItemType Directory -Path $DistDir | Out-Null
}

function Invoke-Tsci {
    param([string[]]$Arguments)

    & $Tsci @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "tscircuit failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

Write-Host "Exporting schematic SVG..." -ForegroundColor Cyan
Invoke-Tsci @("export", "-f", "schematic-svg", "-o", "dist/schematic.svg", "index.circuit.tsx")

Write-Host "Exporting PCB layout SVG..." -ForegroundColor Cyan
Invoke-Tsci @("export", "-f", "pcb-svg", "-o", "dist/pcb.svg", "index.circuit.tsx")

Write-Host "Exporting Gerbers ZIP..." -ForegroundColor Green
Invoke-Tsci @("export", "-f", "gerbers", "-o", "dist/gerbers.zip", "index.circuit.tsx")

Write-Host "Exporting KiCad project archive..." -ForegroundColor Yellow
Invoke-Tsci @("export", "-f", "kicad_zip", "-o", "dist/kicad.zip", "index.circuit.tsx")

Write-Host "Exporting 3D GLB model..." -ForegroundColor Magenta
Invoke-Tsci @("export", "-f", "glb", "-o", "dist/carrier_board.glb", "index.circuit.tsx")

Write-Host "`nAll tscircuit artifacts exported successfully to $DistDir." -ForegroundColor Green
Get-ChildItem $DistDir | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
