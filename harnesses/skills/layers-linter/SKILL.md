---
name: layers-linter
description: Enforces Python layered architecture with the layers-linter CLI (LA001/LA002/LA020). Authors or updates layers.toml, runs the linter, and fixes illegal imports between layers or restricted libraries. Use when adding architecture linting, editing layers.toml, changing cross-layer imports, or when the user mentions layers-linter, la-linter, clean architecture layers, or forbidden library usage.
---

# layers-linter

Tool: [pavelmaksimov/layers-linter](https://github.com/pavelmaksimov/layers-linter) (PyPI `layers-linter`, Python >= 3.11).
Skill: take from this catalog (`harnesses/skills/layers-linter/`), not from upstream.

Parses Python AST, builds an import graph, and checks it against `layers.toml`: which modules belong to which layer, which layers may import which, and which third-party packages are allowed where.

## Install the tool

```bash
uvx layers-linter --help
# or: pip install layers-linter / uv tool install layers-linter
# Flake8 plugin: pip install 'layers-linter[flake8]'
```

Entry points: `layers-linter` and `la-linter` (same CLI).

## When to use

- Introduce architecture linting to a Python repo
- Add or move a module: assign it to a layer in `layers.toml`
- Change imports that cross layers or pull in SQLAlchemy / FastAPI / similar
- Diagnose CI / local `LA001`, `LA002`, `LA020`

After any import or package-layout change in a layered project, re-run the linter before finishing.

## Run

```bash
# PATH must be the top-level package directory (last path segment = import root)
uvx layers-linter src/mypackage
uvx layers-linter mypackage --config layers.toml
uvx layers-linter mypackage --no-check-no-layer
```

Module names are `parent_of(PATH)`-relative, so `layers-linter mypackage` yields `mypackage.foo.bar`. Put those dotted names in `contains_modules`. Passing the git root usually prefixes an extra directory and mismatches the config.

Default config file: `layers.toml` in the current working directory (not necessarily next to the package). CLI checks unlayered modules (**LA002**) unless `--no-check-no-layer`.

Exit code is the number of problems; messages go to stderr:

```text
mypackage/presentation/api.py:12: Invalid layer dependency: 'presentation' -> 'infrastructure'
mypackage/utils/helpers.py: Module 'mypackage.utils.helpers' does not belong to any layer
mypackage/domain/service.py:3: Layers [domain] cannot use restricted library 'sqlalchemy'
```

## Workflow

1. Read existing `layers.toml` if present. Match its layer names; do not invent a parallel `domains/` scheme.
2. If introducing the linter: copy sibling `layers.toml` to the repository root
   (substitute `project` if the package name differs), **ask before writing**.
3. Run the CLI on the package directory.
4. Fix every finding (see below). Prefer moving the import or depending on an interface over widening `depends_on` / `allowed_in`.
5. Widen the allowlists only with explicit user approval.
6. Overlapping `contains_modules` raises `ValueError` (not an LA code). Narrow patterns or use per-layer `exclude_modules` until each module is in exactly one layer.
7. Done when the CLI exits 0 (or the remaining findings are approved exceptions in config).

## `layers.toml`

Canonical template: sibling `layers.toml` (`project/` + `components/`, matching
`python-structure`). Copy to the repository root; substitute the package name if
needed. Do not keep a parallel `domains/` layout.

### Layers

| Field | Meaning |
|---|---|
| `contains_modules` | `fnmatch` patterns on dotted module names |
| `depends_on` | Closed allowlist of layers this layer may import |
| `exclude_modules` | Drop matches from **this** layer only (they may still join another layer) |
| `description` | Ignored by the linter |

`depends_on` values:

- omitted or `"none"` — no layer-to-layer restriction
- `[]` — may not import any other layer
- `["usecases", "libs"]` — only those layers

The allowlist is closed **including same-layer**. Intra-layer imports need the layer's own name in `depends_on`, or omit `depends_on`.

Global `exclude_modules` removes files from analysis entirely (no LA002, no import edges).

Patterns: `mypackage.mod` exact; `mypackage.mod.*` children; `mypackage.*.endpoints` one segment; `*.utils` suffix. `*` in `fnmatch` also matches dots.

### Libraries (`[libs.<package>]`)

Section name is the **importable package** (`sqlalchemy`, `fastapi`), not a layer. `allowed_in` lists **layers** that may import it (prefix match: `sqlalchemy.orm` counts as `sqlalchemy`).

- Lib absent from `[libs]` — unrestricted
- `allowed_in` omitted / `"none"` — unrestricted
- `allowed_in = ["adapters"]` — only those layers; everywhere else is **LA020** (including modules with no layer)

Old key `upstream` is accepted as an alias of `allowed_in`; write `allowed_in`.

## Error codes

| Code | Meaning | Fix |
|---|---|---|
| **LA001** | Layer A imported layer B, B not in A's `depends_on` | Move code, invert via an interface in an allowed layer, or (approved) add B to `depends_on` |
| **LA002** | Module matched no layer (CLI / Flake8 default on) | Add a `contains_modules` pattern, or global-exclude generated/tests packages |
| **LA020** | Import of a restricted third-party package | Move the import to an `allowed_in` layer, or (approved) add the current layer to `allowed_in` |

## Analyzer notes

- Imports inside `if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:` are ignored
- `from . import sibling` (no module name) is skipped; `from .foo import bar` and absolute imports are checked
- Only `.py` files under PATH; module path uses `/` → `.` from the parent of PATH

## Flake8 (optional)

```ini
[flake8]
select = LA
la-config = layers.toml
```

```bash
flake8 mypackage --la-config layers.toml
```

Flake8 always enables the LA002 check. Default `la-config` is `layers.toml`.
