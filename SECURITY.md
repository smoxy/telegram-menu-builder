# Security Policy

`telegram-menu-builder` is alpha software (Development Status :: 3 - Alpha). We take
security seriously and appreciate responsible disclosure.

## Supported Versions

As an alpha-stage project, only the latest `0.x` release receives security fixes.
There are no long-term-support branches yet.

| Version       | Supported          |
| ------------- | ------------------ |
| latest `0.x`  | :white_check_mark: |
| older `0.x`   | :x:                |

If you are running an older release, please upgrade to the latest `0.x` before
reporting an issue.

## Reporting a Vulnerability

**Please do not open public GitHub issues for security vulnerabilities.** Public
issues disclose the problem before a fix is available and put other users at risk.

Instead, report privately using one of the following channels:

1. **GitHub Security Advisory (preferred).** Go to the repository's
   [Security tab](https://github.com/smoxy/telegram-menu-builder/security/advisories)
   and click **"Report a vulnerability"**. This opens a private advisory visible only
   to the maintainers and lets us collaborate on a fix and coordinated disclosure.
2. **Email.** Contact the maintainer at **info@sf-paris.dev**. If possible, include
   "telegram-menu-builder security" in the subject line.

When reporting, please include as much of the following as you can:

- A description of the vulnerability and its potential impact.
- Steps to reproduce, ideally with a minimal code snippet.
- The affected version(s) and your environment (Python version, dependency versions).
- Any suggested remediation, if you have one.

### Response expectations

This is a small, volunteer-maintained alpha project. We aim to:

- **Acknowledge** your report within 7 days.
- **Provide an initial assessment** (severity, whether it is in scope) within 14 days.
- **Release a fix** for confirmed, in-scope vulnerabilities as quickly as is
  practical, and credit you in the advisory unless you prefer to remain anonymous.

These are best-effort targets, not contractual guarantees.

## Scope & Known Accepted Items

The following are known design decisions that are **not** considered vulnerabilities.
Please do not report them as such:

- **MD5 in `encoding.py`.** The `CallbackEncoder` uses MD5 only to compute a
  deterministic 12-character deduplication key for stored callback payloads. It is
  **not** used for any cryptographic, authentication, or integrity purpose, and it is
  invoked with `hashlib.md5(..., usedforsecurity=False)` to make that intent explicit.
  Collision resistance is not a security requirement for this key.
- **Decoded callback parameters are untrusted input.** Callback data is validated as
  well-formed JSON when decoded, but the library does **not** and cannot vouch for the
  *semantic* trustworthiness of the contained values. Telegram callback data
  originates from clients and should be treated as untrusted input. Handlers must
  validate, authorize, and sanitize any decoded parameters (e.g. IDs, indices, flags)
  before acting on them — exactly as you would with any other external request data.

If you find a way to escalate beyond these documented behaviors (for example, code
execution, storage backend compromise, or denial of service through crafted callback
data), that **is** in scope — please report it privately as described above.

## Dependency CVE Tracking

We track vulnerabilities in our dependency tree through:

- **Dependabot**, which runs weekly to open pull requests for vulnerable or outdated
  dependencies (see `.github/dependabot.yml`).
- **`pip-audit`** in CI, which fails the build on known advisories for the resolved
  dependency set (see the `security` job in `.github/workflows/ci.yml`).

See [`docs/dependency-audit.md`](docs/dependency-audit.md) for the current audit
status and history.

One notable example: the `pydantic` floor is pinned to `>=2.4` to exclude
**CVE-2024-3772**, a ReDoS in pydantic's email validation that was fixed in 2.4.0.
The library does not use `EmailStr`, so it was never exploitable here; the floor bump
is defense-in-depth.
