# Security Policy

!!! note "Canonical source"
    This page is a documentation mirror of the project's security policy. The
    canonical policy lives in [`SECURITY.md`](https://github.com/smoxy/telegram-menu-builder/blob/main/SECURITY.md)
    at the repository root. If the two ever disagree, the repo-root file wins.

`telegram-menu-builder` is **alpha** software (`Development Status :: 3 - Alpha`).
Treat the public API as unstable and review each release before upgrading.

## Supported Versions

During the alpha phase only the **latest `0.x` release** receives security fixes.
There are no long-term-support branches and no backports to older `0.x` lines.

| Version    | Supported          |
| ---------- | ------------------ |
| Latest 0.x | :white_check_mark: |
| Older 0.x  | :x:                |

When a vulnerability is fixed, the fix ships in the next `0.x` release and the
advisory is published against that version.

## Reporting a Vulnerability

Please report security issues **privately** — do not open a public issue for a
suspected vulnerability.

Preferred channel:

1. Use GitHub's private vulnerability reporting: go to the repository's
   [**Security** tab](https://github.com/smoxy/telegram-menu-builder/security)
   and click **"Report a vulnerability"** to open a private security advisory.
2. Alternatively, email the maintainer at **info@sf-paris.dev**.

When reporting, please include:

- A description of the issue and its impact.
- The affected version(s) and environment (Python version, dependency versions).
- A minimal reproduction or proof of concept, if available.

### Expected response time

- **Acknowledgement:** within **72 hours** of your report.
- **Initial assessment:** within **7 days**, including whether the report is
  accepted and a rough remediation timeline.

As an alpha project maintained by a single author, timelines are best-effort.
Coordinated disclosure is appreciated — please give the maintainer reasonable
time to ship a fix before any public disclosure.

## Known accepted items

These are reviewed and intentionally accepted. They are **not** vulnerabilities.

!!! info "MD5 dedup key in `encoding.py`"
    `CallbackEncoder._generate_key()` uses `hashlib.md5(...)` to derive a
    deterministic 12-character storage key, purely to **deduplicate** identical
    callback payloads. It is **not** used for any security or integrity purpose.
    The call passes `usedforsecurity=False` to make that intent explicit and to
    satisfy security linters (Bandit `B324`). No secret or trust decision depends
    on this hash.

!!! warning "Treat decoded callback params as untrusted input"
    Callback data round-trips through Telegram, so it can be replayed or tampered
    with by a client. On decode, `CallbackEncoder` JSON-validates the payload and
    reconstructs a `MenuAction`, but **the contents of `params` are caller-supplied
    values, not authenticated data**. Your handlers must still treat decoded
    parameters as untrusted: validate ranges, re-check authorization, and never
    trust an ID or flag in `params` to grant access on its own.

## Dependency CVE tracking

Runtime dependencies are audited on a recurring basis. See the
[Dependency Audit](dependency-audit.md) page for the current findings, the
package-by-package status table, and how to reproduce the audit locally.

Automation in place:

- **Weekly Dependabot** scans for vulnerable and outdated dependencies.
- **CI `pip-audit`** runs on every push/PR and on a schedule, failing the build
  on a known-vulnerable dependency.

The dependency floors are chosen with security in mind — for example, the
`pydantic` floor is pinned to `>=2.4` to exclude `CVE-2024-3772`. Details are in
the [Dependency Audit](dependency-audit.md).
