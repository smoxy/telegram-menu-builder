# Dependency Audit

**Audit date:** 2026-06-03

This page records the dependency and CVE audit for `telegram-menu-builder`. It
complements the [Security Policy](security.md) and is the target of the
"dependency CVE tracking" link there.

## Cadence

Dependencies are audited:

- **On every release** — a manual review is part of the release checklist.
- **Weekly via Dependabot** — automated scans for vulnerable and outdated
  dependencies open PRs/alerts.
- **In CI via `pip-audit`** — runs on every push/PR and on a schedule.

!!! note "CI upgrades pip first"
    CI upgrades `pip` (and its packaging tooling) **before** running `pip-audit`.
    Vulnerabilities in pip's own tooling are reported against the build
    environment, not against this library's dependency surface; upgrading first
    keeps those out of the audit so the signal stays focused on our actual
    runtime dependencies.

## Runtime dependencies

### `python-telegram-bot` (`>=20.0,<22.6`)

No known CVEs affect the imported surface of `python-telegram-bot` within this
range. The **upper bound (`<22.6`) is a compatibility ceiling, not a security
pin** — it caps the range to versions verified against this library's API usage,
and is raised deliberately as new releases are validated.

### `pydantic` (`>=2.4,<3.0`)

**`CVE-2024-3772`** — a Regular-Expression Denial of Service (ReDoS) in
pydantic's **email-validation regex**, fixed in **2.4.0**.

- The previous floor (`>=2.0`) permitted the vulnerable `2.0`–`2.3` releases.
- This library does **not** use email validation: it only depends on
  `BaseModel`, `Field`, `field_validator`, `model_validator`, and `ConfigDict`.
  It never imports `EmailStr` or any email type, so the vulnerable code path was
  **never reachable here**.
- The floor was nonetheless raised to **`>=2.4`** as **defense-in-depth**, so a
  transitive or downstream resolver cannot pull a vulnerable pydantic into an
  environment that installs this package.

## Internal note: MD5 in `encoding.py`

`CallbackEncoder._generate_key()` calls `hashlib.md5(..., usedforsecurity=False)`
to build a deterministic dedup key. This is a **non-cryptographic** use — no
security or integrity decision depends on it. Bandit's `B324` (insecure hash)
finding is handled via the `[tool.bandit]` configuration in `pyproject.toml`,
which documents the rationale inline. See the
[Security Policy](security.md#known-accepted-items) for the accepted-item entry.

## Status table

| Package               | Version range     | Latest known CVE                          | Status                | Action                                                        |
| --------------------- | ----------------- | ----------------------------------------- | --------------------- | ------------------------------------------------------------- |
| python-telegram-bot   | `>=20.0,<22.6`    | None affecting imported surface           | :white_check_mark: OK | Upper bound is a compatibility ceiling; raise as validated.   |
| pydantic              | `>=2.4,<3.0`      | `CVE-2024-3772` (ReDoS, email validation) | :white_check_mark: OK | Floor `>=2.4` excludes vulnerable `2.0`–`2.3`; not exploitable here (no `EmailStr`). |

## How to run the audit locally

Using `pip-audit` directly:

```bash
pip-audit
```

Using the Makefile target:

```bash
make audit
```

Or run the **`dependency-audit` Claude skill**, which performs the same review,
refreshes this page's findings, and reconciles the status table with the current
`pyproject.toml` constraints.
