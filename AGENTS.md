# AGENTS.md

Agent-oriented guide for `telegram-menu-builder`. **Read `CLAUDE.md` first** — it has the
architecture map, command list, conventions, and the encoding/async details.

## Golden rules

1. Run `make type-check` and `make test` before claiming a task is done. Both `mypy src`
   and `pyright` must be green.
2. Never weaken the type-checker config (`mypy strict`, `pyright typeCheckingMode=strict`).
   No blanket `# type: ignore`, no leaking `Any`.
3. Keep 100-char lines and Google-style docstrings on every new or changed public API.
   Builder mutators return `Self`.
4. Use conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `ci:`, ...).
5. This is a published PyPI package. Treat any public-API change as potentially breaking
   and record it under `## [Unreleased]` in `CHANGELOG.md`.

## Subagents (`.claude/agents/`)

| Agent | Trigger |
| --- | --- |
| `type-strictness-reviewer` | After writing or editing any `src/` code, before committing. Runs mypy/pyright/ruff/black checks, verifies docstrings + `Self` returns, flags `# type: ignore` / `Any`. |
| `test-author` | When adding a feature or when coverage drops. Writes class-based pytest tests matching repo conventions, aiming for 90%+ coverage on changed modules. |
| `ptb-compat-checker` | Before bumping the python-telegram-bot or Python bounds, or when reviewing a dependency PR. Verifies the PTB `>=20.0,<22.6` range and the Python 3.12-only / `typing.Self` policy. |

## Skills (`.claude/skills/`)

| Skill | Trigger |
| --- | --- |
| `release` | "release", "cut a version", "bump to X.Y.Z", "publish". Bumps version + CHANGELOG, runs the full check suite, builds, tags, then stops for manual push/publish. |
| `dependency-audit` | "audit dependencies", "check for CVEs", on a Dependabot PR, or before a release. Runs `pip-audit`, verifies pins, updates `docs/dependency-audit.md`. |
| `add-storage-backend` | "add a storage backend", "implement Redis storage", "implement SQL storage". Scaffolds a `BaseStorage` subclass plus matching tests and docs. |
| `add-example` | "add an example", "demo this feature". Adds a runnable bot under `examples/` matching `examples/simple_menu.py` style. |
