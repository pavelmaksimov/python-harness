# Rubric — telegram-order-bot

Judge the final workspace state against the criteria below. Each criterion is scored
0–4; cite the file paths that carry the evidence.

## centralized handler failure policy

| Score | Meaning |
|---|---|
| 4 | Every handler carries the shared decorator stack with the timeout/retry wrapper outermost and the error-handling wrapper directly beneath it; no handler catches exceptions itself, user-facing retry and failure messages come from the shared helpers, and a slow upstream cannot crash the process. |
| 3 | The stack is applied but in the wrong order on one handler. |
| 2 | Decorators exist while inline try/except logic remains in the handlers. |
| 1 | Only one handler was converted. |
| 0 | Handlers still own their error handling. |

Evidence: `project/components/orders/handlers.py`, the shared Telegram helper module.

## dependency-injected presentation handlers

| Score | Meaning |
|---|---|
| 4 | Handlers resolve their collaborators through the composition root at the point of use, pass no sessions or ORM types anywhere, and the component imports no persistence client. |
| 3 | Container usage is right but a session-typed parameter survives in a helper. |
| 2 | Collaborators are resolved from the container while one handler still receives a session. |
| 1 | Only the import was removed. |
| 0 | Handlers still build sessions. |

Evidence: `project/components/orders/handlers.py`, `project/components/orders/use_cases.py`.

## explicit bot registration

| Score | Meaning |
|---|---|
| 4 | Command handlers are registered in the bot entry point through the library's own handler types, the application is built once with the token read from settings (unwrapped at build time), the event loop is the project's chosen one, and start-up logging is configured before the bot runs. |
| 3 | Registration is right, with one detail missing (for example logging configured after the application is built). |
| 2 | Handlers are registered from inside the component module instead of the entry point. |
| 1 | Registration exists but the bot process was left unchanged. |
| 0 | No registration. |

Evidence: `project/infrastructure/apps/bot.py`.
