# Voice Services v2

This is the focused-local voice stack. It has exactly one component for each
job:

- Wyoming Speech-to-Phrase on container port 10300 for constrained command
  recognition;
- a private acoustic diagnostics and research-retention API on container port
  10400;
- Wyoming Piper on container port 10200.

Wake-word detection runs on the ESP32-S3 with ESPHome microWakeWord. Each local
match opens a fresh encrypted Home Assistant command pipeline, while Home
Assistant owns intent recognition and device actions. The old server-side
openWakeWord service is not part of the active command path.

Whisper is not part of this design. Speech-to-Phrase chooses among a finite set
of supported phrases, so an ambiguous short utterance cannot become an
unrelated lamp or area name. It trains locally from Home Assistant sentence
definitions and the YAML under `custom_sentences/`.

The initial vocabulary accepts `lights on/off`, both verb orders such as
`turn lights off` and `turn off lights` (also `switch`), and the acoustically
distinct fallbacks `lights up/out`. Keep the phrase set small:
closely overlapping singular or repeated variants make the short `on`/`off`
decision less reliable rather than adding useful capability.
To add a command, add one intent and its utterances to a YAML file here, add the
matching Home Assistant `intent_script`, retrain Speech-to-Phrase, validate the
phrases, and only then expose it as supported.

Speech-to-Phrase requires a Home Assistant long-lived access token. Put it only
in the ignored `.env` as `SPEECH_TO_PHRASE_HASS_TOKEN`; never commit or print
it. The first model build downloads tools/models and may take several minutes.

## Acoustic diagnostics

`Dockerfile.speech-to-phrase-diagnostics` derives from the immutable upstream
Speech-to-Phrase 1.4.3 image and replaces only its Kaldi transcription module.
Recognition behavior remains the upstream three-candidate decoder and fuzzy
matcher. The patch additionally writes one atomic WAV/JSON pair per request to
the ignored `data/speech-to-phrase/diagnostics/` directory.

The JSON includes N-best text, acoustic/grammar/total costs, score margin, raw
best path, fuzzy text/cost, final text, word timing and lattice confidence when
the lattice supplies them, plus signal and boundary metrics. The separate
`voice-diagnostics` service serves `/health`, `/api/sessions`,
`/api/sessions/<id>`, `/api/reports`, `/api/reports/<id>`,
`/api/research/status`, and optionally `/audio/<id>.wav`. Review labels and
notes are synchronized with `POST /api/sessions/<id>/review`; completed report
analysis is tracked with `POST /api/reports/<id>/analysis`. It sends
CORS/private-network headers so the ESP-hosted dashboard can use it from
another trusted LAN origin.

The dashboard treats `/api/sessions` as an exhaustive recognition ledger. It
adds each returned record to the review queue even when timestamp/transcript
correlation cannot find a device log row, including `NO_AUDIO_AFTER_VAD`,
`NO_FUZZY_MATCH`, `FUZZY_COST_TOO_HIGH`, and empty-transcript results. Those
diagnostic-only rows retain WAV playback and all decoder/signal evidence; a
later matching device record is merged into the same queue item.

There is deliberately no age-based deletion. The service monitors the raw
diagnostic directory and rolls it over only after it exceeds 200 records or
256 MiB by default. It first takes a lock shared with review updates, embeds
every complete record and synchronized annotation into an immutable,
content-addressed `research-*.json` report, atomically persists that report in
the separate ignored `data/speech-to-phrase/reports/` directory, and only then
removes the covered WAV/JSON and review sidecars. If report creation fails or a
record is incomplete, deletion is paused. Reports contain deterministic review
coverage, confusion pairs, issue counts, signal averages, and threshold-based
recommendations; later Codex conclusions are stored as separate analysis
sidecars so the source report remains unchanged.

Configure the count and storage boundaries with
`SPEECH_DIAGNOSTICS_MAX_RECORDS` and `SPEECH_DIAGNOSTICS_MAX_BYTES`. Do not
expose the diagnostics port through a public router, reverse proxy, or Tunnel:
records contain speech audio and transcripts, and the service accepts local
research annotations. Set `SPEECH_DIAGNOSTICS_SERVE_AUDIO=0` to keep metrics
available while disabling browser WAV playback.

## Safe staging

The example binds to loopback-only alternate ports 11300 and 11200. This avoids
colliding with the deployed services and prevents accidental LAN exposure.
Create an ignored `.env` and change the bind addresses only if Home Assistant
runs in another network namespace and explicitly needs LAN access.

The deployed Home Assistant Container uses host networking for native LAN mDNS
and ESPHome discovery. Its Wyoming config entries continue to use stable
service hostnames, mapped inside the Home Assistant container to each
service's loopback-published host port. Speech-to-Phrase remains bridge-networked
and reaches Home Assistant through `host.docker.internal`; a narrow host
firewall rule permits only that bridge subnet to TCP 8123. This preserves the
normal Compose services without adding an mDNS reflector or proxy.

```sh
cp .env.example .env
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
docker compose logs --tail 100 speech-to-phrase voice-diagnostics piper
```

Point a Wyoming integration at the staging Speech-to-Phrase port, build a
focused Assist pipeline, and run the pause and one-breath phrase matrix. The
deployed installation now uses Speech-to-Phrase as its preferred pipeline STT;
its previous Whisper recognizer is stopped rather than used as a fallback.

## Version policy

Upstream base images are pinned by digest instead of `latest`; the local
Speech-to-Phrase image is reproducibly derived from that pinned base. Renovation
is explicit: pull a candidate image, record its immutable digest, rebuild the
diagnostic patch, run the same command corpus, and only then update this file.
Model, voice, and bounded diagnostic data persist under ignored `data/`.
