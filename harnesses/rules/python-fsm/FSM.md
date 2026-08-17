# State machine helper

Copy this module to `project/libs/fsm.py` when the package does not already define
`StateMachine` / `AsyncStateMachine`.

```python
"""Validated state-machine transitions.

``StateMachine`` + ``transition`` for sync; ``AsyncStateMachine`` + ``atransition`` for async.
Persist state in ``get_state`` / ``set_state`` (or ``aget_state`` / ``aset_state``) — memory, DB, or Redis.
Illegal transitions raise ``TransitionError``.

Example::

    class OrderState(Enum):
        CREATED = "created"
        PAID = "paid"

    class Order(StateMachine):
        def get_state(self) -> OrderState: ...
        def set_state(self, new_state: OrderState) -> None: ...

        @transition(from_states=OrderState.CREATED, to_state=OrderState.PAID)
        def pay(self, amount: float) -> str:
            return f"paid {amount}"
"""

import inspect
from abc import ABC, abstractmethod
from enum import Enum
from functools import wraps
from typing import Callable


class TransitionError(Exception):
    pass


class StateMachine(ABC):
    """Sync state machine. Subclasses persist state in ``get_state`` / ``set_state``."""

    @abstractmethod
    def get_state(self) -> Enum:
        """Return the current state."""

    @abstractmethod
    def set_state(self, new_state: Enum) -> None:
        """Persist the new state."""


class AsyncStateMachine(ABC):
    """Async state machine. Subclasses persist state in ``aget_state`` / ``aset_state``."""

    @abstractmethod
    async def aget_state(self) -> Enum:
        """Return the current state."""

    @abstractmethod
    async def aset_state(self, new_state: Enum) -> None:
        """Persist the new state."""


def transition(from_states: list[Enum] | Enum, to_state: Enum):
    """Declare an allowed sync transition. Use with ``StateMachine``."""
    if isinstance(from_states, Enum):
        from_states = [from_states]

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: StateMachine, *args, **kwargs):
            current_state = self.get_state()

            if current_state not in from_states:
                allowed = ", ".join(str(s.name) for s in from_states)
                msg = f"Cannot call {func.__name__} from {current_state.name}. Allowed states: {allowed}"
                raise TransitionError(msg)

            result = func(self, *args, **kwargs)

            self.set_state(to_state)

            return result

        return wrapper

    return decorator


def atransition(from_states: list[Enum] | Enum, to_state: Enum):
    """Declare an allowed async transition. Use with ``AsyncStateMachine``."""
    if isinstance(from_states, Enum):
        from_states = [from_states]

    def decorator(func: Callable) -> Callable:
        if not inspect.iscoroutinefunction(func):
            msg = f"atransition can only decorate async functions, but {func.__name__} is not async"
            raise TypeError(msg)

        @wraps(func)
        async def wrapper(self: AsyncStateMachine, *args, **kwargs):
            current_state = await self.aget_state()

            if current_state not in from_states:
                allowed = ", ".join(str(s.name) for s in from_states)
                msg = f"Cannot call {func.__name__} from {current_state.name}. Allowed states: {allowed}"
                raise TransitionError(msg)

            result = await func(self, *args, **kwargs)

            await self.aset_state(to_state)

            return result

        return wrapper

    return decorator
```
