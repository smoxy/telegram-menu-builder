# Python Compatibility

This page records the feasibility analysis behind the project's Python-version
policy, so the decision is **intentional and reversible** rather than incidental.

## Current policy

`telegram-menu-builder` is **Python 3.12-only**:

```toml
# pyproject.toml
requires-python = ">=3.12"
```

The classifiers, mypy/pyright `pythonVersion`, and the ruff/black
`target-version` are all set to `3.12` to match.

!!! note "Modern-only by design"
    This is a deliberate stance for an alpha library, not a technical accident.
    The sections below document where the *real* limits are and what it would
    take to widen support, should that ever become desirable.

## Why 3.12

The version floor is driven by the typing features the codebase actually uses.
In order of how high they push the floor:

| Feature in use                          | Example                                  | Minimum stdlib version |
| --------------------------------------- | ---------------------------------------- | ---------------------- |
| `from typing import Self`               | `def add_item(...) -> Self:` (builder.py)| **3.11**               |
| PEP 604 unions (`X \| None`)            | `force_strategy: StorageStrategy \| None`| 3.10                   |
| PEP 585 lowercase generics              | `dict[str, Any]`, `tuple[...]`           | 3.9                    |

The **hard blocker for older versions is `from typing import Self`** in
`builder.py` — `Self` only entered the standard library's `typing` module in
**3.11**. PEP 604 unions need 3.10, and PEP 585 lowercase generics need 3.9.

Crucially, **no 3.12-exclusive syntax is used**: there is no PEP 695 `type`
alias statement and no `class C[T]` / `def f[T]()` generic syntax anywhere in
the package. That means the **true hard floor is actually 3.11**, even though the
declared policy is 3.12-only.

## Path to widen support (if ever desired)

Each lower target requires progressively more work:

=== "Down to 3.11+"
    Lowest effort — the code already runs on 3.11.

    - Lower `requires-python` to `>=3.11`.
    - Add the `3.11` classifier.
    - No source changes needed (`typing.Self` exists in 3.11).

=== "Down to 3.10+"
    Adds a conditional import for `Self`.

    - Replace `from typing import Self` with a guarded import from
      `typing_extensions` on older interpreters, e.g.:

      ```python
      import sys

      if sys.version_info >= (3, 11):
          from typing import Self
      else:
          from typing_extensions import Self
      ```

    - Add a conditional dependency:
      `typing_extensions; python_version < "3.11"`.

=== "Down to 3.9"
    Note: **3.9 reached end of life in October 2025.**

    - Everything required for 3.10+ above, **plus**
    - Add `from __future__ import annotations` to every module so PEP 604 unions
      and other deferred annotations evaluate as strings on 3.9.

In **all** of the above you must also:

- **Expand the CI matrix** to test the newly supported interpreters.
- **Bump tool target-versions** for ruff (`target-version`), black
  (`target-version`), and mypy/pyright (`python_version` / `pythonVersion`) to
  the new floor.

## Decision

**Remain 3.12-only for now.**

Rationale:

- **Modern-only stance** — the library targets current, supported runtimes.
- **Smaller test matrix** — fewer interpreters to build and test against keeps
  CI fast and maintenance light for a single-maintainer project.
- **Alpha status** — there is no compatibility commitment to break, so the floor
  can be lowered later at low cost if real demand appears.

This analysis is recorded here precisely so the policy is a **conscious choice**
that can be revisited and reversed using the path above.
