---
name: keep-a-changelog
description: Create and maintain CHANGELOG.md using Keep a Changelog 1.1.0. Use versioned releases for libraries and date-keyed sections for unversioned projects; update the current entry when a task is refined.
---

# Keep a Changelog 1.1.0

Source of truth: https://keepachangelog.com/en/1.1.0/

Versioned-library companion: https://semver.org/spec/v2.0.0.html

## Choose the changelog mode

Inspect the repository and choose one mode before writing:

- **Versioned library** — use when the project publishes a library or the task prepares a
  library release with a version. Keep work under `## [Unreleased]`; on release, move it to
  `## [X.Y.Z] - YYYY-MM-DD` and follow Semantic Versioning.
- **Dated project** — use for an application, service, or other project without library
  release versions. Use `## [YYYY-MM-DD]` as the section heading, with the date in ISO 8601.
  Add new changes to today's existing section instead of creating another heading.

Do not claim that a dated project follows Semantic Versioning.

## Choose the language

Preserve the language of an existing `CHANGELOG.md`. Before creating a new file when the
repository conventions do not make the language clear, ask which language to use. Keep the
file in that language. Section headings default to English (`Added`, `Changed`, …) unless the
user or existing file uses localized headings.

## File

Maintain `CHANGELOG.md` at the repository root.

Versioned-library skeleton:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- First notable change.
```

Dated-project skeleton:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [YYYY-MM-DD]

### Added

- First notable change.
```

## Types of changes

- `Added` — new features
- `Changed` — changes in existing functionality
- `Deprecated` — soon-to-be removed features
- `Removed` — now removed features
- `Fixed` — bug fixes
- `Security` — vulnerability fixes

Omit empty sections.

## Post-task workflow

1. Open or create `CHANGELOG.md` in the selected mode.
2. Record only notable user- or contributor-facing changes, not raw git noise.
3. In library mode, add the change under `Unreleased`. In project mode, add it under today's
   date section.
4. When the task refines work already represented by an unreleased or same-date entry, edit
   that entry to describe the final behavior instead of adding a duplicate.
5. Call out deprecations, removals, security fixes, and breaking changes explicitly.
6. Keep the latest version or date first and preserve the existing style and language.

Skip the changelog update when the task has no notable external effect.

## Library releases

For a versioned library release:

1. Move relevant `Unreleased` entries into `## [X.Y.Z] - YYYY-MM-DD`.
2. Leave an empty `## [Unreleased]` heading for subsequent work.
3. Keep a section for every released version.
4. Mark yanked releases after the date: `## [0.0.5] - 2014-12-13 [YANKED]`.
5. Add comparison links at the bottom when the project uses git tags.

## Anti-patterns

- Dumping commit log diffs into the changelog
- Adding a second bullet when the current task merely refines the first one
- Using a version heading for an unversioned project
- Claiming SemVer for a project that has no versioned library releases
- Hiding deprecations or breaking changes
- Using ambiguous regional dates instead of `YYYY-MM-DD`
