---
name: dependency-audit
description: Audit dependencies for CVEs and verify version ranges. Use when the user says "audit dependencies", "check for CVEs", on a Dependabot PR, or before a release.
---

# Dependency audit

Audit `telegram-menu-builder`'s dependencies for known CVEs and confirm the version
ranges are still correct.

## Steps

1. **Upgrade pip first**, then run the audit:
   - `python -m pip install --upgrade pip`
   - `pip-audit` (also runnable as `make audit`)

   Upgrading pip first ensures pip's own tooling CVEs are excluded from the report, so
   the findings reflect the project's dependencies rather than a stale pip.
2. **Verify the pins** in `pyproject.toml` match policy:
   - `python-telegram-bot>=20.0,<22.6`
   - `pydantic>=2.4,<3.0`
   - optional extras: `redis>=5.0` `[redis]`; `sqlalchemy>=2.0`, `aiosqlite>=0.19` `[sql]`.
3. **Confirm the known/accepted items** still hold:
   - **pydantic CVE-2024-3772** (ReDoS in email validation, fixed in 2.4.0): the `>=2.4`
     floor excludes it. Grep the codebase to confirm the library does **not** use
     `EmailStr` or any email validation (`grep -ri "EmailStr\|email" src/`); if that's
     still true the issue was never exploitable here and the floor is defense in depth.
   - **MD5 dedup key**: `hashlib.md5(..., usedforsecurity=False)` in `encoding.py` — a
     non-cryptographic key, not a vulnerability. The bandit `B324` finding is
     acknowledged in `[tool.bandit]` in `pyproject.toml`.
4. **Update `docs/dependency-audit.md`**: refresh the dependency/CVE table and bump the
   audit date to today.
5. **Report** a short table (package, current pin, latest, advisories, verdict) and any
   concrete `pyproject.toml` edits needed. Do NOT apply pin changes unless the user asks
   — if a bump touches PTB or the Python floor, defer to the `ptb-compat-checker` agent.

## Output

A short findings table plus, if action is needed, the exact `pyproject.toml` line edits.
