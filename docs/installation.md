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

| Extra        | Installs                                                                                                       | Use for                                                       |
| ------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `[redis]`    | `redis>=5.0`                                                                                                    | Redis-backed short-term/persistent callback storage.          |
| `[sql]`      | `sqlalchemy[asyncio]>=2.0.30,<3.0`, `aiosqlite>=0.19`                                                           | Built-in async SQL storage (`SQLAlchemyStorage`); SQLite ready out of the box. |
| `[postgres]` | `asyncpg>=0.29`                                                                                                 | PostgreSQL/Supabase driver for the SQL backend (add on top of `[sql]`).        |
| `[mysql]`    | `asyncmy>=0.2.9`                                                                                                | MySQL/MariaDB driver for the SQL backend (add on top of `[sql]`).              |
| `[dev]`      | Test, lint, type-check, and build tooling                                                                       | Local development and contributing.                           |
| `[docs]`     | `mkdocs>=1.6`, `mkdocs-material>=9.5`, `mkdocstrings[python]>=0.26`, `mkdocs-include-markdown-plugin>=6.0`       | Building this documentation site.                             |
| `[all]`      | Everything from `[redis]`, `[sql]`, `[postgres]`, and `[mysql]`                                                 | All optional runtime backends in one install.                 |

!!! note "Choosing a SQL driver"
    `[sql]` installs SQLAlchemy together with `aiosqlite`, so SQLite works immediately. Add
    `[postgres]` for PostgreSQL/Supabase (`asyncpg`) or `[mysql]` for MySQL/MariaDB (`asyncmy`)
    — for example `pip install "telegram-menu-builder[sql,postgres]"`. See
    [Storage Backends](guide/storage.md) for the full SQL guide.

```bash
# Examples
pip install "telegram-menu-builder[redis]"
pip install "telegram-menu-builder[sql]"             # SQLite ready
pip install "telegram-menu-builder[sql,postgres]"    # + PostgreSQL/Supabase
pip install "telegram-menu-builder[sql,mysql]"       # + MySQL/MariaDB
pip install "telegram-menu-builder[all]"
pip install "telegram-menu-builder[dev]"
pip install "telegram-menu-builder[docs]"
```

## Next steps

- Follow the [Quick Start](quickstart.md) to build your first menu.
- Read the [Storage Backends](guide/storage.md) guide to choose a storage strategy.
