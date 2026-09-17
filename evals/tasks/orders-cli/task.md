# Task

Operators need an `orders` command-line tool with two commands:

- `orders list` — prints the orders, one per line, so that `orders list | wc -l` is exact;
- `orders cancel <order-id>` — destructive: it asks for confirmation unless the operator
  passes a flag that answers "yes" up front.

Today the commands live in `project/components/orders/cli.py` as an argparse script that
prints everything to stdout and calls the async repository through `asyncio.run`.

Rebuild the command layer the way this project builds CLIs:

- the command tree is declared with the project's CLI framework, with the root program in
  `project/infrastructure/apps/cli.py` and the orders commands in the component's own
  module registered below the root;
- parameters are declared as annotated options/arguments with help text, so `--help` is
  useful without reading the source; enums or literals are used for closed value sets;
- the confirmation prompt has a flag equivalent for scripted use;
- stdout carries data only; progress, prompts and error messages go to stderr;
- application errors become exit code 1 with a short stderr message, usage errors stay 2,
  and unexpected exceptions are not swallowed;
- sync commands drive the async repository through the project's async bridge instead of
  calling the event loop directly.

`uv run python -m project.infrastructure.apps.cli --help` must work offline, and the CLI
must not import anything that opens a network connection at start-up.
