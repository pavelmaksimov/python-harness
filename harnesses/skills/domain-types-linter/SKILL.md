---
name: domain-types-linter
description: Enforces domain-specific types in Python business-logic annotations with the dt-linter CLI (DT001, DT003–DT011, DT100–DT125). Runs the linter on domain packages and replaces primitive/generic annotations with NewType or domain classes. Use when adding domain typing, editing use-case/service annotations, diagnosing DT codes, or when the user mentions domain-types-linter, dt-linter, NewType, or primitive types in domain code.
---

# domain-types-linter

Tool: [pavelmaksimov/domain-types-linter](https://github.com/pavelmaksimov/domain-types-linter) (PyPI `domain-types-linter`, Python >= 3.10).
Skill: take from this catalog (`harnesses/skills/domain-types-linter/`), not from upstream.

Checks type annotations so business logic names domain objects (`UserId`, `Money`) instead of universal types (`str`, `int`, `list[str]`).
Domain `NewType`s live in `project/datatypes.py` (or the repo's existing types module): `NewType("UserIdT", Annotated[int, "User ID"])`.

## Install the tool

```bash
uvx --from domain-types-linter dt-linter --help
# or: pip install domain-types-linter / uv tool install domain-types-linter
# Flake8 plugin: pip install 'domain-types-linter[flake8]'
```

Entry point: `dt-linter`.

## When to use

- Introduce domain-type linting to a Python repo
- Add or change annotations on use cases, domain services, or domain models
- Diagnose CI / local `DT001`, `DT003`–`DT011`, `DT100`–`DT125`

Run it on **domain / use-case / service** packages. Adapters, ORM, Pydantic HTTP schemas, and CLI parsers legitimately use primitives — do not scan the whole repo by default.

After annotation changes in those packages, re-run before finishing.

## Run

```bash
uvx --from domain-types-linter dt-linter path/to/domain_package
uvx --from domain-types-linter dt-linter path/to/file.py
```

PATH is a file or a directory (recursive `*.py`). No config file. Exit code 1 if any finding; success prints `All checks have been successful!`.

```text
mypackage/domains/orders/service.py:
mypackage/domains/orders/service.py:12: DT003 forbidden to use universal type 'str'
mypackage/domains/orders/service.py:18: DT001 forbidden to use alias with universal type 'UserName'
mypackage/domains/orders/service.py:24: DT100 forbidden to use parameterized type without domain type 'list'
```

## Workflow

1. Identify domain packages (use cases, domain services, domain types). Match existing layout; do not invent a parallel domain layer.
2. If introducing the linter: agree the scan paths, **ask before** adding CI / Flake8 `select = DT`.
3. Run `dt-linter` on those paths only.
4. Fix every finding (see below). Prefer `NewType` or a domain class over silencing the check.
5. Done when the CLI exits 0 on the agreed paths.

## Allowed vs forbidden

Forbidden in annotations:

- Universal bases: `str`, `int`, `float`, `complex`, `bytes`, `bytearray`, `Decimal`, `Any`, `AnyStr`
- Alias of a universal base: `UserName = str` then `name: UserName` (**DT001**). `NewType` is not an alias.
- Generics bare or parameterized with universal types: `list`, `list[str]`, `dict[str, int]`, `Optional[int]`, `Iterable[str]`, …

Allowed:

- `bool`, `None`, `bool | None`
- `Callable` / `Awaitable` (with or without parameters)
- `NewType("UserId", int)` and domain classes
- Generics parameterized only with domain types: `list[UserId]`, `dict[UserId, Order]`, `Optional[UserId]`

```python
from typing import NewType

UserId = NewType("UserId", int)
UserName = NewType("UserName", str)

def get_user(user_id: UserId) -> UserName: ...
```

`Union[...]` / `X | Y` is walked: primitives inside still fail. `raise` and runtime values are not checked — only annotations on `FunctionDef` args/returns and `AnnAssign`.

## Error codes

| Code | Meaning | Fix |
|---|---|---|
| **DT001** | Annotation uses an alias of a universal type (`X = str`) | Replace the alias with `NewType("X", str)` or a domain class |
| **DT003** | `str` | `NewType` / domain type |
| **DT004** | `int` | `NewType` / domain type |
| **DT005** | `float` | `NewType` / domain type |
| **DT006** | `complex` | `NewType` / domain type |
| **DT007** | `bytes` | `NewType` / domain type |
| **DT008** | `bytearray` | `NewType` / domain type |
| **DT009** | `Decimal` | domain money/quantity type |
| **DT010** | `Any` | concrete domain type |
| **DT011** | `AnyStr` | domain string `NewType` |
| **DT100–DT125** | Generic bare or filled with universal types (`list`, `dict`, `Optional`, `Iterable`, `Type`, …) | Parameterize with domain types, or replace the generic |

Unknown mapped types surface as **DT999**.

## Flake8 (optional)

```ini
[flake8]
select = DT
```

```bash
flake8 path/to/domain_package --select=DT
```

Limit Flake8 paths the same way as the CLI — do not enable `DT` on infrastructure/schema packages unless the user asks.
