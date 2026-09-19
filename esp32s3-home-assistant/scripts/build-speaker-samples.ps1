# Run with Windows PowerShell, which provides System.Speech. Generates only
# synthetic test phrases; no recordings or network services are used.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$outputDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'audio'
[IO.Directory]::CreateDirectory($outputDir) | Out-Null
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$phrases = @('Speaker test. One, two, three. This is a clear voice sample.', 'The lights are on. Bright sunshine fills the room.')
$lines = [Collections.Generic.List[string]]::new()
$lines.Add('#pragma once')
$lines.Add('#include <cstdint>')
$lines.Add('namespace speaker_samples {')
try {
  for ($clip = 0; $clip -lt $phrases.Count; $clip++) {
    $stream = [IO.MemoryStream]::new()
    $synth.SetOutputToAudioStream($stream, $format)
    $synth.Speak($phrases[$clip])
    $raw = $stream.ToArray()
    # SetOutputToAudioStream emits raw PCM, unlike SetOutputToWaveStream.
    if ($raw.Length -lt 3200 -or $raw.Length % 2) { throw 'Invalid speech PCM' }
    $samples = [int16[]]::new($raw.Length / 2)
    [Buffer]::BlockCopy($raw, 0, $samples, 0, $raw.Length)
    $peak = 1
    foreach ($sample in $samples) { $peak = [Math]::Max($peak, [Math]::Abs([int]$sample)) }
    $lines.Add("// $($phrases[$clip]) Peak normalized to -1 dBFS; 16 kHz mono.")
    $lines.Add("static const int16_t speech_$clip[] = {")
    for ($offset = 0; $offset -lt $samples.Length; $offset += 32) {
      $row = for ($i = $offset; $i -lt [Math]::Min($offset + 32, $samples.Length); $i++) {
        [int][Math]::Round($samples[$i] * 29204.0 / $peak)
      }
      $lines.Add(($row -join ',') + ',')
    }
    $lines.Add('};')
    Write-Host "Speech $clip : $($samples.Length) samples, source peak $peak"
    $stream.Dispose()
  }
} finally { $synth.Dispose() }
$lines.Add('}')
[IO.File]::WriteAllLines((Join-Path $outputDir 'speaker_samples.h'), $lines, [Text.UTF8Encoding]::new($false))
