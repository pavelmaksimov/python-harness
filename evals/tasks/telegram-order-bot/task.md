# Task

The bot process in `project/infrastructure/apps/bot.py` currently exposes no commands, and
`project/components/orders/handlers.py` does everything by hand: each handler catches its
own exceptions, decides its own user-facing text, and builds a database session to pass
into the use case.

Add the order commands support asked for:

- `/start` — greets the user;
- `/status` — reports the caller's current order status through the order status use case.

Bring the bot up to the project's Telegram conventions:

- handlers are presentation only: they resolve their collaborators through the composition
  root, and never import a persistence client, a session factory or an ORM type;
- command registration lives in the bot entry point, not inside the component module;
- failures are handled in one place: the shared decorator stack wraps every handler, with
  the timeout/retry wrapper outermost, so a slow upstream produces a retrying user message
  and the final failure never crashes the bot;
- handler bodies do not swallow exceptions and do not invent their own error text;
- the bot token comes from the project settings and is unwrapped once when the application
  is built.

`uv run python -c "import project"` must work.
