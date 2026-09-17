# Rubric — orders-cli

Judge the final workspace state against the criteria below. Each criterion is scored
0–4; cite the file paths that carry the evidence.

## predictable command tree

| Score | Meaning |
|---|---|
| 4 | The root program lives in the app module and registers the component app explicitly; commands and parameters are declared with the CLI framework's typed metadata, help text is present, closed value sets are typed, and no unknown framework or hand-rolled argument parsing remains. |
| 3 | The tree is right but one parameter is declared without help text or without typing a closed set. |
| 2 | The framework is used while the previous parser survives alongside it, or parameters lost their typing. |
| 1 | Only the entry point was renamed. |
| 0 | The argparse script remains. |

Evidence: `project/infrastructure/apps/cli.py` and the orders CLI module.

## stdout and stderr contract

| Score | Meaning |
|---|---|
| 4 | Data goes to stdout and nothing else does; prompts, confirmations and errors go to stderr; the list command's stdout can be piped and counted exactly. |
| 3 | Contract is right except one stray message on stdout. |
| 2 | Some messages still use plain printing to stdout. |
| 1 | Logging and data are mixed on stdout. |
| 0 | Everything is printed to stdout. |

Evidence: the orders CLI module's output calls.

## safe destructive command flow

| Score | Meaning |
|---|---|
| 4 | The destructive command prompts once with a flag equivalent that skips the prompt, application errors are mapped to exit code 1 through the shared error boundary, and unexpected exceptions propagate. |
| 3 | Prompt and flag are fine, but the error boundary is applied inconsistently (one command lacks it). |
| 2 | A confirmation exists without a non-interactive equivalent, or errors are caught and swallowed. |
| 1 | Confirmation happens after the mutation. |
| 0 | Destructive command runs unconditionally. |

Evidence: the orders CLI module.
