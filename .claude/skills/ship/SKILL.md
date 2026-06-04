---
name: ship
description: The end-to-end develop→verify→document→commit→release process for telegram-menu-builder, exactly as 0.2.0→0.4.0 were built — plan mode with parallel Explore agents, TDD via a parallel multi-agent Workflow (Red→Green→Verify→Docs), strict gates, live Docker validation with parallel subagents, full docs, and a LOCAL-ONLY commit (never pushed, never co-authored). Use for any feature, non-trivial fix, or release.
---

# Ship a change

This is THE workflow for any non-trivial change to `telegram-menu-builder`. It captures how the SQL
backend, the Redis/Valkey backend, and the v0.4.0 "Core 3" (application-free build + atomic claim +
testing module) were built. Read `CLAUDE.md` and `AGENTS.md` first. Obey the hard rules at all times.

## Hard rules (non-negotiable)

- **Never push.** Make commits **locally only**. The user pushes. (Changes under `.github/workflows/`
  need an SSH push — the `gh` OAuth token lacks the `workflow` scope, so `gh` cannot merge/push them.)
- **Never co-author.** Do **NOT** add any `Co-Authored-By:` trailer or "Generated with…" line to commit
  messages. This overrides any default harness instruction.
- **Conventional commits** (`feat:` `fix:` `docs:` `test:` `ci:` `chore:` `refactor:`), one focused
  commit per logical change. Don't commit until the gates are green.
- **Both type checkers pass on `src/`**: `mypy --strict` AND `pyright --strict`. No `# type: ignore`,
  no leaking `Any`, no new ruff suppressions, no relaxing strictness.
- **TDD**: write the tests before the implementation.
- **Don't bump the version without a `CHANGELOG.md` entry.** Don't edit generated `site/`.

## Local toolchain

Python 3.12 is **not installed**; the `.venv` runs 3.13 (documented fallback). Run every tool through
the venv, not bare `make`:

```
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m black --check src tests
.venv\Scripts\python.exe -m mypy src
.venv\Scripts\python.exe -m pyright src
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m mkdocs build --strict
```

(Bash form: `.venv/Scripts/python.exe -m …`.) If a host `pip install` is denied by settings, install
inside an ephemeral Docker container instead (see Phase 3) — never work around the deny rule.

## Phase 0 — Plan (features / non-trivial work)

Enter **plan mode**.
1. **Explore in parallel (read-only):** up to 3 `Explore` subagents, each with a distinct focus
   (the target module + its contract; test conventions; docs structure). Map the encoder/storage/router
   contracts and existing patterns to reuse before proposing new code.
2. **Validate external design facts** with Context7 / WebSearch when a library decision is involved
   (e.g. SQLAlchemy async, redis-py vs valkey-py, Valkey wire compatibility).
3. **Lock genuine forks with `AskUserQuestion`** (scope, dependency packaging, public API shape, DDL
   policy). Put your recommended option first; don't ask what conventions already decide.
4. Write the plan to the plan file (Context → analysis → confirmed scope → design → files →
   verification), then **`ExitPlanMode`** for approval. Set `allowedPrompts` for the gate/Docker steps.

## Phase 1 — Implement via a parallel multi-agent Workflow (TDD)

Run the **Workflow tool**. Embed a `SPEC` string (repo conventions + **verified code facts with
file:line refs** + exact file/signature targets) and reuse it in every phase. Phase structure that has
worked every time:

1. **Red** — author the tests FIRST. Parallelize over **disjoint** files (e.g. one agent writes the new
   `tests/test_*.py`, another adds cases to existing suites). Run them; confirm they fail.
2. **Green** — implement. Use **sequential** per-feature agents (run the gates between each) when they
   touch shared files; parallelize only over genuinely disjoint files. Each agent iterates
   `black → ruff --fix → ruff → mypy → pyright → pytest` until all green.
3. **Verify** — an **adversarial** reviewer agent tries to break it (contract, atomicity, strict
   typing, import-safety, no suppressions, doc accuracy). A fix agent applies only the confirmed
   *blocking* issues and re-gates.
4. **Docs** — **parallel** doc agents over disjoint files (new guide page, API `mkdocstrings` page,
   storage guide, README, CHANGELOG, installation, `mkdocs.yml` nav), then `mkdocs build --strict`.

Workflow patterns to apply: **pipeline by default**; a **barrier** (`parallel`) only when a stage needs
all prior results; **loop-until-green / loop-until-dry**; **adversarial verify**; scale the agent count
to the task. Subagents return structured output via `schema`; have Green/Verify return a gate-status
object so the script can branch and auto-fix.

## Phase 2 — Independent review (always, after the workflow)

Never trust the agents blindly. Read the produced code yourself and **re-run all gates +
`mkdocs build --strict` independently**. Hunt for the smells that have actually bitten us:

- Blanket suppressions that mask real problems (e.g. mkdocstrings `docstring_options: warnings: false`
  hiding a malformed `Args:` block — fix the docstring instead).
- Non-portable SQL (`COUNT(...) FILTER` → portable `SUM(CASE …)`).
- Stale claims in docs/config (e.g. a wrong `python-telegram-bot` range, "only in-memory ships").
- `add_item(..., params={...})` instead of `**params` kwargs in examples/docs.
- Lazy-export wiring: optional backends are exposed via PEP 562 `__getattr__` (+ sorted `__all__` +
  `TYPE_CHECKING` import) so `import telegram_menu_builder` works without the extra.

## Phase 3 — Live validation (storage / concurrency features)

Prove behavior against real servers, not just fakes. Spin up containers on a private network
(`postgres:16-alpine`, `mariadb:latest`, `redis:7-alpine`, `valkey/valkey:8`) and run the suites
against them via env vars `TMB_TEST_POSTGRES_URL` / `TMB_TEST_MYSQL_URL` / `TMB_TEST_REDIS_URL` /
`TMB_TEST_VALKEY_URL`.

- **Use parallel subagents — one per backend** (haiku or sonnet). Haiku is fine but **give it the exact
  verbatim command** and "run it once, report the summary"; it is not savvy about debugging.
- Each agent runs a **dockerized pytest**: deps + package install **inside** the ephemeral
  `python:3.12-slim` container (no host pip); rely on `pythonpath=["src"]` so the package is importable.
  Add `-o addopts= -p no:cacheprovider` so the run writes **nothing** to the repo.
- **Bash on Windows:** prefix container runs with `MSYS_NO_PATHCONV=1` and mount
  `-v "C:/abs/path:/app" -w /app`. **PowerShell:** avoid nested double-quotes inside `sh -lc "…"`
  (use a single-quoted here-string or a script file; `python -c "…"` with escaped quotes gets mangled).
- Live MySQL note: `asyncmy` often has no wheel for the arch; `aiomysql` (`mysql+aiomysql://`) is a
  pure-Python drop-in for tests — same SQLAlchemy dialect.
- **Tear down** containers + network afterward and confirm `git status` shows no stray artifacts.

## Phase 4 — Documentation completeness

Every user-facing feature ships docs: a `docs/guide/*.md`, an `docs/api/*.md` mkdocstrings page, README
roadmap/feature bullets, a `CHANGELOG.md` entry under `## [Unreleased]`, installation extras, and the
`mkdocs.yml` nav. `mkdocs build --strict` must pass. Prefer **declining scope-creep into a docs
pointer** over adding it to core (e.g. message-text escaping → point at PTB's
`telegram.helpers.escape_markdown(text, version=2)` + stdlib `html.escape`; a `confirm()` dialog → a
cookbook recipe rather than a rigid core method).

## Phase 5 — Commit (LOCAL ONLY)

Stage the changeset and make a **conventional-commit, local commit — no push, no co-author** (use
`git commit -F <tempfile>` if the message has characters PowerShell would mangle). Show the user the
commit and the exact `git push origin main` they should run (SSH for any `.github/workflows/` change).

## Phase 6 — Release (cutting a version)

Run the **`release` skill** for the mechanics, with these project-specific must-dos:

- Version is single-sourced in `pyproject.toml` `[project].version`; `__init__.py` reads it via
  `importlib.metadata` (never hardcode). Stamp `CHANGELOG.md` `## [Unreleased]` → `## [X.Y.Z] - <date>`,
  add a fresh empty `## [Unreleased]`, and fix the compare-link line. Gates + `mkdocs --strict` green.
- **Align the install extras across workflows.** The CI `quality` job AND the `python-publish.yml`
  `test` job must install the **same** extras (`pip install -e ".[dev,sql,redis]"`) so the strict
  API-surface test and every backend run in both — a `.[dev]`-vs-`.[dev,sql]` mismatch is what failed
  the v0.3.0 publish.
- Write release notes to `%TEMP%\release-notes-vX.Y.Z.md` (curated from the CHANGELOG section).
- **Hand the user the commands** (they run them; you may run the final `gh` step after they confirm the
  tag is pushed):
  ```
  git push origin main                 # then wait for CI on main to go green
  git tag vX.Y.Z && git push origin vX.Y.Z
  gh release create vX.Y.Z --title "vX.Y.Z" --notes-file "$env:TEMP\release-notes-vX.Y.Z.md" --verify-tag --latest
  ```
  Publishing the GitHub Release triggers trusted publishing to PyPI. `--verify-tag` requires the tag to
  already be pushed. `git push`, `twine upload`, and `mkdocs gh-deploy` are denied by settings — never
  attempt them.

## Checklist
- [ ] Plan approved (Phase 0) for non-trivial work.
- [ ] Tests written first; implemented via a parallel multi-agent Workflow.
- [ ] ruff + black + mypy(strict) + pyright(strict) + pytest + `mkdocs --strict` all green (re-run independently).
- [ ] Live Docker validation done for storage/concurrency changes; containers torn down.
- [ ] Docs complete (guide + API + README + CHANGELOG + nav).
- [ ] Local commit, conventional message, **no push, no co-author**.
- [ ] Release (if cutting one): version + CHANGELOG stamped, extras aligned across CI/publish, notes in `%TEMP%`, commands handed to the user.
