---
name: patch-linter
description: Forbids unittest.mock.patch and pytest monkeypatch in tests with the patch-linter CLI (PATCH001). Runs the linter on test paths and replaces patches with injected fakes/stubs. Use when adding patch linting, writing or changing tests that mock collaborators, diagnosing PATCH001, or when the user mentions patch-linter, unittest.mock.patch, or monkeypatch.
---

# patch-linter

Tool: [pavelmaksimov/patch-linter](https://github.com/pavelmaksimov/patch-linter) (PyPI `patch-linter`, Python >= 3.11).
Skill: take from this catalog (`harnesses/skills/patch-linter/`), not from upstream.

Static check for tests: no `unittest.mock.patch` and no pytest `monkeypatch` mutations.
Prefer injecting fakes/stubs (or `Container.local(...)`) over reaching into other modules.

Pairs with `python-tests` (no-patch rule). Overlaps with `di-linter` DI002 when that
optional linter is also installed — both are fine; this skill is the dedicated PATCH001 tool.

## Install the tool

```bash
uvx patch-linter --help
# or: pip install patch-linter / uv tool install patch-linter
# Flake8 plugin: pip install 'patch-linter[flake8]'
```

Entry point: `patch-linter`.

## When to use

- Introduce patch linting to a Python repo
- Write or change tests that would mock collaborators
- Diagnose CI / local `PATCH001`

After test changes that touch mocks, re-run before finishing.

## Run

```bash
uvx patch-linter tests/
uvx patch-linter tests/test_modules tests/test_e2e
uvx patch-linter tests/test_modules/test_foo.py
```

PATH is one or more test files or directories. No config file. Exit code 1 if any finding;
success prints `All checks have been successful!`.

```text
/abs/path/to/tests/test_foo.py:12:5: PATCH001 Patch usage in tests: @patch('module.function')
```

## Workflow

1. Agree the test paths (usually `tests/` or `tests/test_modules/` + `tests/test_e2e/`).
2. If introducing the linter: **ask before** adding CI / Flake8 `select = PATCH`.
3. Run `patch-linter` on those paths.
4. Fix every finding (see below). Prefer injecting a fake over `# noqa: PATCH001`.
5. Suppress a line only with explicit user approval (`# noqa: PATCH001` or bare `# noqa`).
6. Done when the CLI exits 0 (or remaining lines are approved exceptions).

## What is flagged

**PATCH001** — in scanned files:

| Pattern | Example |
|---|---|
| `unittest.mock.patch` | `@patch(...)`, `with patch(...)` |
| Import aliases | `from unittest.mock import patch as p` → `p(...)` |
| Via module | `mock.patch(...)`, `unittest.mock.patch(...)` |
| Patch helpers | `patch.object` / `patch.dict` / `patch.multiple` / `patch.stopall` |
| pytest monkeypatch | `monkeypatch.setattr(...)`, `setenv`, `delattr`, … |

Not flagged (by design): `mocker` (pytest-mock), bare `Mock` / `MagicMock`,
freezegun, your own functions named `patch`, HTTP `client.patch(...)`.

## Fixes

```python
def process_data(repository):
    return repository.get_all()


def test_process_data():
    class FakeRepo:
        def get_all(self):
            return [1, 2, 3]

    assert process_data(FakeRepo()) == [1, 2, 3]
```

With the DI stack: `with Container.local(repo=FakeRepo()):` — still no `patch`.
Freeze "now" with `python-freezegun` (`freeze_time`), not `patch(datetime)`.

## Error codes

| Code | Meaning | Fix |
|---|---|---|
| **PATCH001** | `patch` / `monkeypatch` in tests | Inject a fake/stub; do not patch |

## Flake8 (optional)

```ini
[flake8]
select = PATCH
```

```bash
flake8 --select=PATCH tests/
```

Limit Flake8 to test paths the same way as the CLI.
