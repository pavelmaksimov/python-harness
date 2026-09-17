"""Bot process entry point."""

import asyncio

import uvloop
from telegram.ext import ApplicationBuilder
from telegram.request import HTTPXRequest

from project.settings import Settings


async def run_bot_app() -> None:
    application = (
        ApplicationBuilder()
        .token(Settings().TELEGRAM_BOT_TOKEN.get_secret_value())
        .request(HTTPXRequest())
        .build()
    )

    async with application:
        await application.start()
        await asyncio.Event().wait()


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(run_bot_app())
