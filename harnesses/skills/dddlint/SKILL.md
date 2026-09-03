---
name: dddlint
description: MUST USE for editing dddlint.yaml
---

# dddlint

Tool: [benomahony/dddlint](https://github.com/benomahony/dddlint) (PyPI `dddlint`).
Skill and `dddlint.yaml` template: take from this catalog (`harnesses/skills/dddlint/`), not from upstream.

This harness uses dddlint for one rule only: **duplicate** — one name, one
definition in the codebase, so every name greps to exactly one thing. The
vocabulary features (forbidden terms, synonyms, canonical forms, maps,
embeddings, LSP) stay off.

## Install the tool

```bash
uvx dddlint lint --help
# or: uv add --dev dddlint
```

Entry point: `dddlint`.

## When to use

- Introduce name-uniqueness linting to a Python repo
- Add a class, function, method, or variable whose name may already mean something else
- Rename a symbol (the new name must stay unique)
- Diagnose CI / local `duplicate` findings

After adding or renaming a definition, re-run before finishing.

## Run

```bash
uvx dddlint lint                              # from the repo root; reads dddlint.yaml
uvx dddlint lint --config dddlint.yaml
```

Auto-detects each file's language and downloads the tree-sitter grammar on
first run. Honors `.gitignore`; always skips `.git`, `.venv`, `node_modules`,
`__pycache__`, `dist`, `build`, `target`, `vendor`.

Exit codes: **0** no findings, **1** findings, **2** no config found — keep
`dddlint.yaml` at the repository root.

```text
project/components/orders/repositories.py:42 duplicate: 'OrderRepository' also defined at project/components/payments/repositories.py:17
```

`lint` needs no network or embeddings. When `dddlint` is selected at install
time, the rendered `.pre-commit-config.yaml` carries a `dddlint` hook
(pre-commit and pre-push, whole repo, no per-file args); otherwise wire
`uvx dddlint lint` as a CI gate when the user asks.

## Workflow

1. Read existing `dddlint.yaml` if present. Keep its keys; do not add
   vocabulary rules to a uniqueness-only config.
2. If introducing the linter: copy sibling `dddlint.yaml` to the repository
   root, **ask before writing**.
3. Run `dddlint lint` from the repository root.
4. Fix every duplicate (see below). Prefer renaming over `exclude`.
5. Add `exclude` entries only for generated or vendored trees, with explicit
   user approval.
6. Done when the CLI exits 0.

## What is flagged

**duplicate** (warning) — one name is claimed by more than one definition in
the same context. With no `domains` / `contexts` configured, the whole
codebase is one context.

- Matching is exact and case-sensitive; every sharer is reported, each message
  naming the others
- Definitions are classes, functions, methods, variables, and constants — so
  the same method name on two different classes collides, by design
- Dunder names (`__init__`, `__eq__`) and module path names are exempt
- With this config only `duplicate` and `drift` can fire: `forbidden` /
  `synonyms` stay empty and `enforce_canonical` is `false`

**drift** (info) — two definitions whose names split into the same token set
(`get_user_by_id` vs `getUserById`). It cannot be disabled by config; treat it
as a duplicate in disguise and converge on one spelling. It also fails the run
(exit 1).

## Fixes

Rename all but the rightful owner; the new name must itself be unique.

```python
# duplicate: 'Validator' also defined at project/components/users/validator.py
class Validator: ...          # orders component

class OrderValidator: ...     # renamed: says what it validates
```

Do not silence source findings with `exclude`; reserve it for generated or
vendored code (gitignore syntax, relative to `dddlint.yaml`):

```yaml
exclude:
  - migrations/
  - src/generated/
```

Scoping collisions away with `domains` / `contexts` is a vocabulary feature —
out of scope for this harness.

## `dddlint.yaml`

Canonical template: sibling `dddlint.yaml`. Copy to the repository root.
Every key is optional; an empty file is valid and `name_uniqueness` then
defaults to `true`.

| Key | Catalog value | Meaning |
|---|---|---|
| `name_uniqueness` | `true` | Enables `duplicate` — the reason this harness installs dddlint |
| `enforce_canonical` | `false` | Disables `alias` even if synonyms appear later |
| `forbidden` | `[]` | No banned terms — keep empty |
| `synonyms` | `[]` | No canonical vocabulary — keep empty |
| `exclude` | `[]` | Generated / vendored trees only |

## Non-goals

`forbidden` terms, `synonyms` / canonical names, `map` / `export` vocabulary
tracking, and the LSP server are upstream features this harness does not use.
Do not configure them unless the user explicitly widens the scope beyond name
uniqueness.
