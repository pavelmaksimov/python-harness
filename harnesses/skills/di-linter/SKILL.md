---
name: di-linter
description: Detects Python dependency-injection anti-patterns with the di-linter CLI (DI001 in-process construction, DI002 patch in tests). Authors or updates di.toml, runs the linter, and injects project dependencies instead of constructing or patching them. Use when adding DI linting, editing di.toml, constructing project classes inside functions, writing tests with patch/monkeypatch, or when the user mentions di-linter, DI001, DI002, or dependency injection.
---

# di-linter

Tool: [pavelmaksimov/di-linter](https://github.com/pavelmaksimov/di-linter) (PyPI `di-linter`, Python >= 3.11).
Skill: take from this catalog (`harnesses/skills/di-linter/`), not from upstream.

Finds project objects constructed or called inside functions instead of being injected, and patch/monkeypatch usage in tests.

## Install the tool

```bash
uvx di-linter --help
# or: pip install di-linter / uv tool install di-linter
# Flake8 plugin: pip install 'di-linter[flake8]'
```

Entry point: `di-linter`.

## When to use

- Introduce DI linting to a Python repo
- Add a function that uses a project class, repository, or helper
- Write or change tests that mock collaborators
- Diagnose CI / local `DI001`, `DI002`

After constructing project types or adding tests, re-run before finishing.

## Run

PATH must be a Python package directory (`__init__.py` present) — usually the top-level package, not the git root. The package directory name is the import prefix (`project/` → imports `project.*` count as project deps).

```bash
uvx di-linter project
uvx di-linter project --config-path di.toml
uvx di-linter project --exclude-objects Settings Container --exclude-modules 'project.components.*.endpoints'
uvx di-linter project --tests-path tests/test_modules tests/test_e2e
```

`--tests-path` defaults to `tests` and overrides `di.toml`. PATH is required even with `--config-path`.

Exit code 1 if any finding.

```text
project/components/orders/use_cases.py:14: Dependency injection: UserRepository()
tests/test_modules/test_orders.py:8: Patch usage in tests: @patch('project.components.orders.repositories.UserRepository')
```

## Workflow

1. Read existing `di.toml` if present. Keep its exclude patterns; do not invent a parallel scheme.
2. If introducing the linter: copy sibling `di.toml` to the repository root
   (substitute `project` if the package name differs), **ask before writing**.
   Keep its exclude patterns; do not invent a parallel scheme. Patch companion
   rules that already pair other linters so they mention `di-linter`:

```text
python-structure pairing:
  Pair with `layers-linter` and `domain-types-linter`.
  → Pair with `layers-linter`, `di-linter`, and `domain-types-linter`.
python-di Tests bullet (if that rule is present):
  Pair with `di-linter` (DI001 in-process construction, DI002 patch in tests).
python-tests (if present), after the no-patch sentence:
  Pair with `di-linter` (DI002).
```
3. Run the CLI on the package directory.
4. Fix every finding (see below). Prefer injecting a parameter over excludes or `# di: skip`.
5. Widen `exclude-objects` / `exclude-modules` or add `# di: skip` only with explicit user approval.
6. Done when the CLI exits 0 (or the remaining findings are approved exceptions).

## What is flagged

**DI001** — inside a function/method, a **project** dependency is used without being a parameter:

- Constructing or calling a class/function **defined in the same file**
- Constructing, calling, or reading attributes of an import whose module starts with the package prefix
- `with project_cm():` (the context manager itself is the dependency)

Not flagged:

- Stdlib / third-party (`FastAPI()`, `Path()`, `datetime.now()`)
- Name passed in as a function parameter
- Nested functions defined in the same function
- Names bound by `with ... as name`
- Calls in `raise ...`
- Line containing `# di: skip`

**DI002** (CLI only) — in `--tests-path` files: `patch(...)`, `@patch`, `monkeypatch.setattr`, or any call whose name/attribute is `patch` or `monkeypatch`.

## Fixes

```python
# DI001 — inject
def process_data(repository: UserRepository) -> None:
    repository.get_all()

# DI002 — pass a fake; do not patch
def test_process(fake_repository):
    process_data(fake_repository)
```

Composition root (container, settings accessor, HTTP endpoints that wire the graph) may need excludes. Keep use cases and domain services strict.

```python
repository = UserRepository()  # di: skip
```

## `di.toml`

Optional. Search order: `--config-path`, else `./di.toml`, else `di.toml` next to the project root.

Canonical template: sibling `di.toml` (`project/` + `components/`, matching
`python-structure` and `python-di`). Copy to the repository root; substitute
the package name if needed. Composition root is excluded; use cases and domain
services stay strict.

`exclude-objects` and `exclude-modules` use `fnmatch` (`*` wildcards), **case-insensitive**.

| Key | Matches against |
|---|---|
| `exclude-objects` | The dependency **name** in the finding (`UserRepository`, `local_func`) |
| `exclude-modules` | Dotted path of the **file being checked**, not the imported module |

To ignore uses of an imported helper, exclude the object name (or the file that uses it). `project-root` in docs is informational; the CLI derives the prefix from PATH.

## Error codes

| Code | Meaning | Fix |
|---|---|---|
| **DI001** | Project dependency used inside a function without injection | Pass it as a parameter; construct only at the composition root |
| **DI002** | `patch` / `monkeypatch` in tests | Inject a fake/stub; do not patch |

## Flake8 (optional)

The plugin reports **DI001 only**. Use the CLI for **DI002**.

```ini
[flake8]
select = DI
di-config = di.toml
di-exclude-objects = Settings,Container
di-exclude-modules = project.container,project.components.*.endpoints
```

```bash
flake8 project --select=DI --di-config di.toml
```
