# CLI command helpers

Copy this module to `project/infrastructure/base/cli.py` when the package does not already
define `run_async` / `cli_errors`. Command modules import these helpers; they do not
catch-and-print errors themselves. `AppError` comes from `project/exceptions.py`
(`python-architecture/python-exceptions.mdc`).

```python
import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import typer
import uvloop
from rich.console import Console

from project.exceptions import AppError

logger = logging.getLogger(__name__)

err_console = Console(stderr=True)


def run_async(awaitable):
    """Bridge a sync Typer command to async collaborators. Commands stay `def`."""
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        return runner.run(awaitable)


def cli_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Outermost command decorator: AppError -> stderr message + exit code 1.

    Unexpected exceptions propagate — Typer prints the Rich traceback.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except AppError as exc:
            logger.info("Command %s failed: %s", func.__name__, exc)
            err_console.print(f"Error: {exc}")
            raise typer.Exit(1) from exc

    return wrapper
```

Usage in `project/components/{name}/cli.py` (decorator order is bottom-to-top; `@wraps` keeps
the signature Typer parses for CLI parameters):

```python
from typing import Annotated

import typer

from project.container import Container
from project.infrastructure.base.cli import cli_errors, run_async

app = typer.Typer()


@app.command()
@cli_errors
def create(name: Annotated[str, typer.Argument(help="User name to create.")]) -> None:
    """Create a user."""
    user = run_async(Container().create_user_use_case.run(name))
    print(user.id)
```
