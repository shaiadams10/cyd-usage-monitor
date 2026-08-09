# Security Policy

Do not open a public issue containing credentials, authorization URLs or
codes, account identifiers, private endpoints, routing IDs, logs, or profile
data.

For a vulnerability in a public GitHub copy of this repository, use GitHub's
private vulnerability reporting flow on the repository **Security** tab. Give
the affected component, impact, reproduction steps, and a minimal redacted
example. If private reporting is not enabled, ask the maintainers to enable it
without disclosing the vulnerability details publicly.

Security fixes should include regression tests and must preserve the boundary
between provider CLI profiles, dashboard credentials, the CYD device token,
and optional alert credentials.
