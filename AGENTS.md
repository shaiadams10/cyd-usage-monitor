# ESP32 Workspace Guidelines

This repository contains independent ESP32 projects. Keep changes scoped to
the relevant project directory and read that project's `AGENTS.md` before
editing.

## Public-repository rules

1. Never commit credentials, API keys, Wi-Fi credentials, access tokens,
   session data, device identifiers, private hostnames, private IP addresses,
   email addresses, or personal filesystem paths.
2. Keep real configuration in ignored files such as `.env` and
   `include/secrets.h`. Commit only safe, value-free examples.
3. Keep generated firmware, dependency caches, runtime data, CLI profiles,
   logs, and local editor settings out of version control.
4. Use configurable environment variables or documented placeholders for
   deployment-specific paths and endpoints.
5. Update the affected project's `README.md` and `CHANGELOG.md` with every
   behavior, configuration, authentication, deployment, UI, or hardware
   change.
6. Run the relevant build, tests, and smoke checks before handoff. Deploy only
   to an environment explicitly identified by the project operator; do not
   embed a deployment target in the repository.

Each project must be self-contained, document its hardware and pin mapping,
and retain its own build configuration.
