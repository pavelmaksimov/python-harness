---
name: cli-design
description: MUST USE for designing a new command-line tool, reviewing CLI command structure, scriptability, output contract, or distribution — before building or materially changing a CLI's interface. Pairs with the python-typer rule, which owns the code.
---

# CLI design

Design patterns and failure modes for command-line tools, adapted from
microsoft/amplifier-bundle-systems-design (`system-type-cli-tool`). The `python-typer` rule
owns the code-level harness; this skill decides the interface. Read it before writing
commands, and at review time for CLI UX and compatibility.

## Should this be a CLI at all?

| Need | Build |
|---|---|
| Developers run it by hand, locally or in CI | CLI |
| Another program consumes the result | library or API, not a CLI |
| Runs on a schedule or in the background | worker, not a CLI |
| Humans browse and operate data | admin UI, not a CLI |

One tool, one job. `curl`/`jq` stay single-purpose; `git`/`kubectl` are subcommand trees.

## Command structure

- Subcommand tree (`tool resource action`) when there are more than ~5 distinct operations
  with different flag sets. Two levels is the practical limit; three only when the grouping
  is obvious; four means redesign. Single-purpose tools get no subcommands.
- Positional arguments are the primary noun — at most two. Everything that modifies behavior
  is a flag. If users read `--help` to remember which positional is which, they should be
  flags.
- POSIX short flags (`-v`) pair with GNU long flags (`--verbose`; hyphens, not underscores);
  booleans get `--x / --no-x`, never `--x=true`; support both `--opt value` and `--opt=value`.
- `--` separates flags from positional user input — mandatory for tools that pass arbitrary
  user input through.
- Global flags (`--verbose`, `--config`, `--output`) are defined once at the root and stay
  few and universal; command-specific flags stay local.

## Scriptability contract

- stdout is data, stderr is messages. `tool list | wc -l` must be correct; progress bars,
  warnings, and diagnostics never touch stdout.
- Accept `-` as a filename for stdin/stdout; support `cat f | tool process` and
  `tool process < f`.
- Every interactive prompt has a flag equivalent (`--yes`, `--name=foo`). When stdin is not a
  TTY, never prompt — fail and name the flag. A CI run hanging on a prompt is an incident.
- Provide `--output json` (or `--json`) beside human output. Human tables may change any
  release; the JSON schema is the stable contract. Respect `NO_COLOR` / `--color=auto|never`.
- Exit codes are API: 0 success, 1 failure, 2 usage. Add more only when callers branch on
  them, and document them; never above 125.

## Configuration

Precedence: flags → environment (`TOOL_NAME` convention) → project config → user config
(`~/.config/tool/`, XDG) → compiled defaults. Every layer is optional; the first run must
work with zero files on disk. Prefer TOML for config files. Support `--config path`, and
provide `tool config show` that prints resolved values with the source of each.

## Errors and UX

Every error answers: what happened, why, what to do next. Suggest corrections for typos
(`tool biuld` → `tool build`). Destructive operations get `--dry-run` with output specific
enough to predict exactly what will happen, and a confirmation with a bypass flag. Bounded
work reports counts; unbounded work reports activity — on stderr. `--verbose` adds context;
`--debug` dumps diagnostics for bug reports.

## Compatibility

People script against your output. JSON schema, exit codes, flag names, env var names, and
config keys are semver-protected: removing or renaming is a major bump; new subcommands,
flags, and fields are minor. Human-facing formatting may change in minors. Deprecate flags
with a stderr warning one minor before removal; never silently change flag semantics.

## Distribution (Python)

`[project.scripts]` entry plus `uv tool install` for isolated use; pin versions in CI
(`tool==1.2.3`, never `latest`). Shell completion comes from the framework
(`--install-completion`). Single-binary packaging (PyInstaller and similar) only when a real
consumer needs it.

## Anti-patterns (reject at review)

| Anti-pattern | Fix |
|---|---|
| Banners, tips, update notices on every run | quiet by default; opt into noise |
| Flag salad with no subcommand structure | command tree |
| Prompts without flag equivalents; color without `--no-color` | scriptable tool |
| Exit 0 after a failed operation | non-zero exit, loud failure |
| Status messages on stdout | stderr |
| Config file required for basic operations | zero-config first run |
| One binary doing builds + deploys + monitoring | separate tools, shared library |
| REPL where subcommands suffice | compose with the shell |
| Undocumented env vars changing behavior | list them in `--help` and docs |

## When not to apply

Long-running inbound services (HTTP, bot) have their own adapters and rules. This skill is
for tools invoked from a shell; revisit distribution and compatibility choices only when a
real consumer appears.
