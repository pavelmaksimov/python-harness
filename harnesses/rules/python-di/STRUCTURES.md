# LazyInit and LazyService

Copy this module to `project/libs/structures.py` when the package does not already define
`LazyInit` / `LazyService`.

```python
import importlib
import typing as t
from contextlib import contextmanager
from contextvars import ContextVar

_UNSET = object()


def import_object(path: str) -> t.Any:
    """Import an object from a ``module.path:qualname`` string."""
    module_path, qualname = path.split(":", 1)
    module = importlib.import_module(module_path)
    obj = module
    for part in qualname.split("."):
        obj = getattr(obj, part)
    return obj


class LazyInit[T]:
    """Process-wide lazy singleton with ``local()`` (ContextVar) and ``override()`` (process) for tests."""

    def __init__(self, klass: type[T], kwargs_func: t.Callable[[], dict] | None = None) -> None:
        self._klass: type[T] = klass
        self._kwargs_func: t.Callable[[], dict] = kwargs_func or dict
        self._singleton: T | None = None
        self._local: ContextVar[T | object] = ContextVar(
            f"lazy_init_local_{klass.__name__}_{id(self)}",
            default=_UNSET,
        )

    def __call__(self) -> T:
        local = self._local.get()
        if local is not _UNSET:
            return local  # type: ignore[return-value]
        if self._singleton is None:
            self._singleton = self._klass(**self._kwargs_func())
        return self._singleton

    def reset(self) -> None:
        self._singleton = None

    def __getattr__(self, item: str) -> t.Any:
        is_method = isinstance(getattr(self._klass, item), t.Callable)
        error = "Access to attributes and methods of this class is carried out through a class call."
        raise AttributeError(
            (
                f"{error}\n{self._klass.__name__}.{item}() -> {self._klass.__name__}().{item}()"
                if is_method
                else f"{error}\n{self._klass.__name__}.{item} -> {self._klass.__name__}().{item}"
            ),
        )

    def _current_kwargs(self) -> dict[str, t.Any]:
        current = self._local.get()
        if current is not _UNSET and hasattr(current, "model_dump"):
            return current.model_dump()
        if self._singleton is not None and hasattr(self._singleton, "model_dump"):
            return self._singleton.model_dump()
        return {}

    @contextmanager
    def local(self, **kwargs: t.Any):
        token = self._local.set(self._klass(**(self._kwargs_func() | self._current_kwargs() | kwargs)))
        try:
            yield
        finally:
            self._local.reset(token)

    @contextmanager
    def override(self, **kwargs: t.Any):
        origin = self._singleton
        self._singleton = self._klass(**(self._kwargs_func() | kwargs))
        try:
            yield
        finally:
            self._singleton = origin


class LazyService[T]:
    """Non-data descriptor: ``LazyService("pkg.mod:Class")`` or ``LazyService(lambda s: ...)``."""

    def __init__(self, factory: type[T] | str | t.Callable[..., T]) -> None:
        self._factory = factory

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @staticmethod
    def _instantiate(factory: type[T] | str | t.Callable[..., T], container: t.Any) -> T:
        if isinstance(factory, str):
            target = import_object(factory)
            if isinstance(target, type):
                return target()
            if callable(target):
                return target()
            return target
        if isinstance(factory, type):
            return factory()
        return factory(container)

    def __get__(self, obj: t.Any | None, objtype: type | None = None) -> T:
        if obj is None:
            return self  # type: ignore[return-value]
        if self._name not in obj.__dict__:
            obj.__dict__[self._name] = self._instantiate(self._factory, obj)
        return obj.__dict__[self._name]
```
