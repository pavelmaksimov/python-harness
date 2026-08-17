# Telegram handler helpers

Copy this module to `project/infrastructure/utils/telegram.py` when the package does not already
define `processing_errors` / `timeout_with_retry`. Handlers import these decorators; they do not
catch-and-reply errors themselves.

`AuthError` comes from `project/exceptions.py` (`python-exceptions`). Add `check_auth` only when the
repo already has an auth collaborator — do not add one here.

```python
import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from project.exceptions import AuthError

logger = logging.getLogger(__name__)

failed_message = "Something went wrong. Error code {log_id}"
processing_retry_message = "Timed out. Retrying..."
processing_message_with_retry = "Processing... (max wait {timeout}s)"


def processing_errors(func):
    """Central place to catch handler failures. Handlers must not swallow exceptions."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            return await func(update, context)

        except AuthError as exc:
            user_id = update.effective_user.id if update.effective_user else "unknown"
            logger.info("User %s is not authenticated", user_id)
            if update.effective_message:
                await update.effective_message.reply_text(text=str(exc))

        except Exception:
            log_id = update.effective_user.id if update.effective_user else "unknown"
            logger.exception("Handler %s failed log_id=%s", func.__name__, log_id)
            if update.effective_message:
                await update.effective_message.reply_text(failed_message.format(log_id=log_id))

    return wrapper


def timeout_with_retry(
    func: Callable | None = None,
    *,
    timeout: float = 180,
    max_attempts: int = 3,
    retry_message: str | None = processing_retry_message,
    failed_message: str | None = failed_message,
    processing_message_on: bool = False,
):
    """Timeout the handler and retry. Must wrap `processing_errors` (outermost)."""

    def decorator(wrapped: Callable) -> Callable:
        @wraps(wrapped)
        async def wrapper(*args, **kwargs) -> Any:
            for arg in args:
                if isinstance(arg, Update):
                    update: Update = arg
                    break
            else:
                error = "Update not found in args"
                raise ValueError(error)

            processing_msg = None
            if processing_message_on:
                processing_msg = await update.effective_message.reply_text(
                    processing_message_with_retry.format(timeout=timeout),
                )
                await update.effective_message.chat.send_chat_action("typing")

            for attempt in range(max_attempts):
                try:
                    return await asyncio.wait_for(wrapped(*args, **kwargs), timeout=timeout)

                except TimeoutError:
                    if attempt == max_attempts - 1:
                        if failed_message:
                            log_id = update.effective_chat.id if update.effective_chat else "unknown"
                            await update.effective_message.reply_text(failed_message.format(log_id=log_id))
                        raise

                    logger.warning(
                        "Timeout Error in %s (attempt %s/%s)",
                        wrapped.__name__,
                        attempt + 1,
                        max_attempts,
                    )
                    if retry_message:
                        await update.effective_message.reply_text(retry_message)

                finally:
                    if processing_msg:
                        await processing_msg.delete()
                        processing_msg = None

            error = f"timeout_with_retry exhausted attempts in {wrapped.__name__}"
            raise TimeoutError(error)

        return wrapper

    if func is not None:
        return decorator(func)

    return decorator
```

Usage in `project/components/{name}/handlers.py` (decorator order is bottom-to-top):

```python
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from project.container import Container
from project.infrastructure.utils.telegram import processing_errors, timeout_with_retry


@timeout_with_retry
@processing_errors
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    container = Container()
    await container.example_use_case.run(update.effective_user.id)
    await update.effective_message.reply_text("Hello")


def register_example_handlers(application) -> None:
    application.add_handler(CommandHandler("start", start_handler))
```
