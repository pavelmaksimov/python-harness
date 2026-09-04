# CLI app entry

Copy this module to `project/infrastructure/apps/cli.py` when the package does not already
define the CLI program. Helpers come from `project/infrastructure/base/cli.py`
(sibling `CLI_HELPERS.md`). Register component apps here; keep use-case logic in use cases.
Call `setup_logging()` once at process start (`python-architecture/python-logging.mdc`; copy
`LOGGER.md` from `.cursor/rules/python-architecture/` into `project/logger.py` if missing).

```python
import importlib.metadata
import logging
import signal
import sys
from typing import Annotated

import typer

from project.components.example.cli import app as example_app
from project.logger import setup_logging

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,  # default — never enable in repos with secrets
)


def _version_callback(value: bool) -> None:
    if value:
        print(importlib.metadata.version("project"))  # substitute the package name
        raise typer.Exit


@app.callback()
def root_callback(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Verbose logging on stderr."),
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = None,
) -> None:
    """One-line tool description shown in --help."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def _route_logs_to_stderr() -> None:
    """setup_logging() defaults to a stdout console handler; CLI stdout is data only."""
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setStream(sys.stderr)


def main() -> None:
    if hasattr(signal, "SIGPIPE"):  # POSIX: die silently when the pipe closes (`… | head`)
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    setup_logging()
    _route_logs_to_stderr()
    app()


# Component commands: without a name they join the top level, with a name they nest.
app.add_typer(example_app)


if __name__ == "__main__":
    main()
```

Entry point in `pyproject.toml` (points at `main`, not `app`, so logging and the POSIX pipe
contract are configured first):

```toml
[project.scripts]
tool-name = "project.infrastructure.apps.cli:main"
```
