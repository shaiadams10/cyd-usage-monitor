# Contributing

Keep each ESP32 project self-contained and follow the workspace and project
`AGENTS.md` files before changing code.

1. Create an ignored `.env` and `include/secrets.h` from their examples.
2. Never place real accounts, credentials, authorization artifacts, private
   endpoints, routing identifiers, host paths, logs, or device identifiers in
   commits, tests, screenshots, issues, or pull requests.
3. Pin new dependencies and document hardware, configuration, behavior, and
   deployment changes in the affected README and changelog.
4. Run the server tests, Compose validation, PlatformIO build, and WebAssembly
   rebuild when relevant.

For this project, the baseline checks are:

```sh
python -m unittest discover -s cyd-usage-monitor/server -v
cd cyd-usage-monitor
docker compose --env-file .env.example config --quiet
pio run
```

On Windows, rebuild the browser simulator with
`simulator/build-wasm.ps1`; the generated JavaScript and WebAssembly files must
be committed together.
