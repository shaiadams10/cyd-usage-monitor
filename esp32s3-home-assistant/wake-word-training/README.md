# On-device Hey Burden microWakeWord

This workspace trains a streaming, quantized microWakeWord model for ESPHome.
It deliberately does **not** reuse the deployed `hey_burden.tflite` binary:
that artifact targets openWakeWord on the Home Assistant server and is not
compatible with ESPHome's on-device microWakeWord interpreter.

The new trainer reuses the private WSL corpus already produced for Hey Burden:
20,000 positive clips, 20,000 confusable/hard-negative clips, held-out tests,
and 500 room/background clips. Generated features, virtual environments, and
model checkpoints remain under `~/.cache/hey-burden-training` in WSL. Final
artifacts remain ignored because the source datasets have mixed licenses and
the model is intended for personal deployment.

Run from PowerShell:

```powershell
.\wake-word-training\setup-micro-wake-word.ps1
.\wake-word-training\train-micro-wake-word.ps1 -Stage all
```

Resume an interrupted training phase with:

```powershell
.\wake-word-training\train-micro-wake-word.ps1 -Stage train -Resume
```

Both launchers derive the WSL home and repository paths at runtime. Override
`-WslDistro` or `-CacheRoot` when using a different distribution or cache
location.

Do not switch `device.yaml` until `artifacts/hey_burden.tflite` and
`artifacts/hey_burden.json` exist and the exported streaming model has passed
its held-out false-accept/recall evaluation.

The current quantized streaming export uses cutoff `0.87`: the independent
test measured zero false accepts/hour and 11.7% false rejection there. Cutoff
`0.86` reduced false rejection to 11.2% but measured two false accepts/hour, so
the conservative value is the deployment default.
