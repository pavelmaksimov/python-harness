---
name: conventional-commits
description: Draft and validate commit messages using Conventional Commits 1.0.0. Use when writing commits, fixing commit message format, choosing type/scope, or marking breaking changes.
---

# Conventional Commits 1.0.0

Source of truth: https://www.conventionalcommits.org/en/v1.0.0/

## Format

```text
<type>[optional scope][!]: <description>

[optional body]

[optional footer(s)]
```

## Required meaning

- `fix` — bug fix (SemVer PATCH)
- `feat` — new feature (SemVer MINOR)
- `BREAKING CHANGE` footer, or `!` after type/scope — breaking API change (SemVer MAJOR)
- Other types are allowed (`build`, `chore`, `ci`, `docs`, `style`, `refactor`, `perf`, `test`, …) and have no implicit SemVer effect unless they include a breaking change
- Scope is optional and sits in parentheses: `feat(parser): …`

## Spec rules to enforce

1. Prefix with a type noun, optional scope, optional `!`, then `: ` and description.
2. Use `feat` for new features and `fix` for bug fixes.
3. Scope, if present, is a noun in parentheses after the type.
4. Description is a short summary immediately after `: `.
5. Body is optional; if present, start it one blank line after the description.
6. Footers are optional; start them one blank line after the body.
7. Footer token uses `-` instead of spaces (`Acked-by`), except `BREAKING CHANGE`.
8. Mark breaking changes with `!` before `:` and/or a `BREAKING CHANGE: …` footer.
9. If `!` is used, the description may describe the break and the footer may be omitted.
10. Treat tokens as case-insensitive except `BREAKING CHANGE`, which must be uppercase.
11. `BREAKING-CHANGE` in a footer is synonymous with `BREAKING CHANGE`.

## Workflow

1. Inspect the staged/unstaged diff and infer the dominant intent.
2. Prefer one intent per commit. If the change mixes intents, split commits when possible.
3. Choose `feat` / `fix` / another type; add scope only when it clarifies the area.
4. Write a concise description focused on why/intent, not a file list.
5. Add a body only when context, migration notes, or rationale are needed.
6. Add `BREAKING CHANGE: …` or `!` when the public API or behavior breaks.
7. Return the final message ready to paste into `git commit`.

## Examples

```text
feat: allow provided config object to extend other configs

BREAKING CHANGE: `extends` key in config file is now used for extending other config files
```

```text
feat(api)!: send an email to the customer when a product is shipped
```

```text
fix: prevent racing of requests

Introduce a request id and a reference to latest request. Dismiss
incoming responses other than from latest request.

Refs: #123
```

```text
docs: correct spelling of CHANGELOG
```

## FAQ defaults

- Initial development: write commits as if the product is already released.
- Casing: any casing is allowed; stay consistent (prefer lowercase types).
- Multiple types in one change: split into multiple commits when possible.
- Wrong type before release: rewrite history if the workflow allows; after release, follow project process.
- Reverts: a common pattern is `revert: …` plus `Refs: <sha>, <sha>`.
