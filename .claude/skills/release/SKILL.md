---
name: release
description: Cut a new release of telegram-menu-builder. Use when the user says "release", "cut a version", "bump to X.Y.Z", or "publish". Bumps version in pyproject.toml + CHANGELOG.md (and verifies __init__.py reads it via importlib.metadata), runs the full check suite, builds, and tags.
---

# Release

Cut a new release of `telegram-menu-builder`. This skill prepares and tags the release
locally; it deliberately **stops before** pushing or publishing.

## Preconditions

- Working tree is clean (`git status` shows nothing to commit). If dirty, stop and ask
  the user to commit or stash first.
- You are on the default branch (`main`) or a release branch the user named.
- `[Unreleased]` in `CHANGELOG.md` has entries describing what's shipping. If it's
  empty, stop and ask what changed.

## Steps

1. **Decide the SemVer bump** from the `## [Unreleased]` section of `CHANGELOG.md`:
   - `Added`/`Changed` (backward-compatible) -> MINOR.
   - breaking/`Removed`/incompatible `Changed` -> MAJOR (note: pre-1.0 alpha, so
     breaking changes may still go in a MINOR — confirm intent with the user).
   - `Fixed` only -> PATCH.
   Confirm the target `X.Y.Z` with the user.
2. **Bump `pyproject.toml`**: set `[project].version = "X.Y.Z"`.
3. **Update `CHANGELOG.md`**: rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`
   (today's date), add a fresh empty `## [Unreleased]` above it, and update/add the
   version compare links at the bottom of the file.
4. **Verify `__init__.py`** still reads the version via
   `importlib.metadata.version("telegram-menu-builder")` — there is NO hardcoded version
   to bump there. If someone hardcoded one, fix it back to `importlib.metadata`.
5. **Run the full check suite** and ensure everything is green:
   `make format && make lint && make type-check && make test && make audit`.
6. **Build and verify the artifacts**: `make build` then `twine check dist/*`.
7. **Commit**: `git commit -am "chore(release): vX.Y.Z"`.
8. **Tag**: `git tag vX.Y.Z`.
9. **STOP.** Do not push and do not publish automatically. Tell the user to run
   `git push --follow-tags` and to create the GitHub Release (CI publishes to PyPI from
   the published Release / tag). `twine upload`, `mkdocs gh-deploy`, and `git push` are
   denied by `.claude/settings.json` — that is intentional.

## Checklist

- [ ] Clean working tree confirmed.
- [ ] SemVer bump decided from `[Unreleased]` and confirmed with user.
- [ ] `pyproject.toml` version set to `X.Y.Z`.
- [ ] `CHANGELOG.md` section renamed + dated, new empty `[Unreleased]`, compare links updated.
- [ ] `__init__.py` confirmed to use `importlib.metadata` (no hardcoded version).
- [ ] `make format && make lint && make type-check && make test && make audit` all pass.
- [ ] `make build` + `twine check dist/*` pass.
- [ ] Commit `chore(release): vX.Y.Z` created.
- [ ] Tag `vX.Y.Z` created.
- [ ] Stopped; told user to `git push --follow-tags` and create the GitHub Release.
