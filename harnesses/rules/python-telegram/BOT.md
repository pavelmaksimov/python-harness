# Telegram bot entry

Copy this module to `project/infrastructure/apps/bot.py` when the package does not already define
the bot process. Token comes from `Settings().TELEGRAM_BOT_TOKEN` (`python-settings`). Register
component handlers here; do not put use-case logic in this file.
Call `setup_logging()` once at process start (`python-logging`; copy `LOGGER.md` into `project/logger.py`
if missing).

Use the default `HTTPXRequest()`. When `python-monitoring` is installed, pass
`TelegramHTTPXTransportWithMonitoring` via `HTTPXRequest(httpx_kwargs={"transport": ...})` and
decorate handlers with `action_tracking_decorator("…_handler")` inside `processing_errors`.

```python
import asyncio

import uvloop
from telegram.ext import AIORateLimiter, ApplicationBuilder
from telegram.request import HTTPXRequest

from project.logger import setup_logging
from project.settings import Settings


def register_handlers(application) -> None:
    """Call each component's register_*_handlers(application) here."""


async def run_bot_app() -> None:
    setup_logging()

    application = (
        ApplicationBuilder()
        .token(Settings().TELEGRAM_BOT_TOKEN.get_secret_value())
        .request(HTTPXRequest())
        .rate_limiter(AIORateLimiter(max_retries=3))
        .concurrent_updates(True)  # noqa: FBT003
        .build()
    )

    register_handlers(application)

    async with application:
        await application.start()
        try:
            async with application.updater:
                await application.updater.start_polling()
                try:
                    await asyncio.Event().wait()
                finally:
                    await application.updater.stop()
        finally:
            await application.stop()


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(run_bot_app())
```
