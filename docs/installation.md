# Installation

## Requirements

Telegram Menu Builder targets **Python 3.12 or newer** (`requires-python = ">=3.12"`). This is a
deliberate decision that lets the library use modern typing features. See
[Python Compatibility](python-compatibility.md) for the full feasibility analysis.

## Install from PyPI

```bash
pip install telegram-menu-builder
```

This installs the core library together with its runtime dependencies:

- `python-telegram-bot>=20.0,<22.6`
- `pydantic>=2.4,<3.0`

!!! note "Why the pydantic floor is `>=2.4`"
    The pydantic floor is raised to `2.4` as defense-in-depth to exclude
    [CVE-2024-3772](dependency-audit.md), a ReDoS in pydantic's email validation that was fixed in
    `2.4.0`. The library does **not** use `EmailStr`, so it was never exploitable here, but the
    floor bump keeps the dependency tree clean. See the
    [Dependency & CVE Audit](dependency-audit.md) for details.

## Optional extras

Install optional features with the standard `pip` extras syntax, for example
`pip install "telegram-menu-builder[redis]"`.

| Extra     | Installs                                                                                                       | Use for                                              |
| --------- | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `[redis]` | `redis>=5.0`                                                                                                    | Redis-backed short-term/persistent callback storage. |
| `[sql]`   | `sqlalchemy>=2.0`, `aiosqlite>=0.19`                                                                            | SQL-backed persistent callback storage.              |
| `[dev]`   | Test, lint, type-check, and build tooling                                                                       | Local development and contributing.                  |
| `[docs]`  | `mkdocs>=1.6`, `mkdocs-material>=9.5`, `mkdocstrings[python]>=0.26`, `mkdocs-include-markdown-plugin>=6.0`       | Building this documentation site.                    |
| `[all]`   | Everything from `[redis]` and `[sql]`                                                                            | All optional runtime backends in one install.        |

```bash
# Examples
pip install "telegram-menu-builder[redis]"
pip install "telegram-menu-builder[sql]"
pip install "telegram-menu-builder[all]"
pip install "telegram-menu-builder[dev]"
pip install "telegram-menu-builder[docs]"
```

## Next steps

- Follow the [Quick Start](quickstart.md) to build your first menu.
- Read the [Storage Backends](guide/storage.md) guide to choose a storage strategy.
