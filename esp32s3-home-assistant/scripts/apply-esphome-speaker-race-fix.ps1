$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $PSScriptRoot
$speakerSource = Join-Path $projectDir ".venv/Lib/site-packages/esphome/components/i2s_audio/speaker/i2s_audio_speaker.cpp"
$marker = "// Local workaround: do not initialize the locked I2S bus twice while the task starts."
$speakerSchema = Join-Path $projectDir ".venv/Lib/site-packages/esphome/components/i2s_audio/speaker/__init__.py"
$stereoMarker = "# Local workaround: a configured stereo DAC must reject mono streams so upstream duplicates both slots."

if (-not (Test-Path -LiteralPath $speakerSource)) {
  throw "ESPHome runtime not found at $speakerSource"
}

$source = [System.IO.File]::ReadAllText($speakerSource)
if ($source.Contains($marker)) {
  Write-Host "ESPHome speaker startup workaround is already applied."
} else {
  $needle = @"
      if (this->status_has_error()) {
        break;
      }

      if (this->start_i2s_driver(this->audio_stream_info_) != ESP_OK) {
"@
  $replacement = @"
      if (this->status_has_error()) {
        break;
      }

      $marker
      if (this->speaker_task_handle_ != nullptr) {
        break;
      }

      if (this->start_i2s_driver(this->audio_stream_info_) != ESP_OK) {
"@

  if (-not $source.Contains($needle)) {
    throw "The ESPHome speaker source no longer matches 2026.7.0; review whether the upstream race is fixed."
  }

  [System.IO.File]::WriteAllText(
    $speakerSource,
    $source.Replace($needle, $replacement),
    [System.Text.UTF8Encoding]::new($false)
  )
  Write-Host "Applied the ESPHome 2026.7 speaker startup workaround."
}

if (-not (Test-Path -LiteralPath $speakerSchema)) {
  throw "ESPHome speaker schema not found at $speakerSchema"
}

$schema = [System.IO.File]::ReadAllText($speakerSchema)

# Assist response audio is fixed 16 kHz mono PCM. A previous workaround forced
# Home Assistant toward stereo while VoiceAssistant itself retained mono stream
# metadata, which corrupted spoken output. Remove it when present.
if ($schema.Contains($stereoMarker)) {
  $schema = $schema.Replace(
@"
    $stereoMarker
    min_output_channels = 2 if config[CONF_CHANNEL] == CONF_STEREO else 1

"@,
""
  ).Replace("            min_channels=min_output_channels,", "            min_channels=1,")
  [System.IO.File]::WriteAllText($speakerSchema, $schema, [System.Text.UTF8Encoding]::new($false))
  Write-Host "Removed the incompatible forced-stereo Assist workaround."
  exit 0
}

$schemaNeedle = @"
    if config[CONF_I2S_MODE] == CONF_PRIMARY:
        # Primary mode can reconfigure the bus to the incoming sample rate and channel count.
        audio.set_stream_limits(
            min_bits_per_sample=min_bits_per_sample,
            max_bits_per_sample=max_bits_per_sample,
            min_channels=1,
            max_channels=2,
"@
Write-Host "ESPHome uses native mono Assist stream negotiation; no stereo workaround applied."
