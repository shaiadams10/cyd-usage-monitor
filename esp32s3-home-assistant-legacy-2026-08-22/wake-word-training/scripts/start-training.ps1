[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$trainerUrl = "https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing"

Write-Host "Opening Home Assistant's official openWakeWord trainer..."
Write-Host $trainerUrl
Start-Process -FilePath $trainerUrl

