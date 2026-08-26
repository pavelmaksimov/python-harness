# Coverage tables for pyproject.toml

Merge these tables into the target repo-root `pyproject.toml`. Copy only
missing tables/keys; preserve existing values and ask before replacing any of
them. Substitute `project` if the package root differs.

```toml
[tool.coverage.run]
source = ["project"]
branch = true
omit = [
    "*/__main__.py",
    "*/migrations/*",
    "*/alembic/*",
]

[tool.coverage.report]
fail_under = 95
show_missing = true
skip_covered = true
precision = 2
exclude_also = [
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

Notes:

diff-cover does not read `[tool.coverage.*]` or any pyproject table of its own:
the skill passes `--compare-branch` / `--fail-under` as CLI flags (see
`SKILL.md`). No diff-cover table belongs in `pyproject.toml`.

- `fail_under = 95` is the catalog default; a target repo may set its own
  threshold — the gate always reads the value from this table.
- `exclude_also` extends coverage.py's built-in excludes instead of
  replacing them; do not convert it to `exclude_lines`.

