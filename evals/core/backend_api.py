"""Stable boundary between orchestration backends and per-experiment execution."""
from dataclasses import dataclass
import importlib.util
from pathlib import Path
from typing import Protocol

from .selection import Selection


@dataclass(frozen=True)
class RunRequest:
    """One experiment request, frozen so a backend cannot mutate the selection.

    ``subject_command`` / ``judge_command`` are overrides the core prepends to the
    exact OpenCode invocation it builds for the profile it chose: a launcher for
    the transcript shim or the test suite, never a model choice. A fallback
    profile therefore needs no second launcher, and a real run leaves them
    ``None``.
    """

    task_id: str
    include: tuple[int, ...]
    exclude: tuple[int, ...]
    selection: Selection
    subject_profile: str
    judge_profile: str
    workdir: Path
    run_id: str
    repo_root: Path
    source_commit: str
    knowledge_revision: str
    subject_command: tuple[str, ...] | None = None
    judge_command: tuple[str, ...] | None = None


@dataclass
class BackendResult:
    run_id: str
    status: str
    artifact_dir: Path
    manifest_path: Path | None
    attempts: list[dict]
    error: str | None


class Backend(Protocol):
    name: str
    version: str

    def doctor(self, *, repair: bool = False) -> dict: ...
    def run(self, request: RunRequest) -> BackendResult: ...
    def status(self, run_id: str) -> dict: ...


def discover_backends(repo_root: Path) -> dict[str, Backend]:
    """Load repository-owned adapters, never an independently maintained registry."""
    found = {}
    for path in sorted((repo_root / 'evals/backends').glob('*/backend.py')):
        if path.is_symlink() or not path.resolve().is_relative_to(repo_root.resolve()):
            raise ValueError('Backend paths must remain inside the repository')
        spec = importlib.util.spec_from_file_location(
            f'evals.backends.{path.parent.name}.backend', path
        )
        if spec is None or spec.loader is None:
            raise ValueError(f'Cannot import backend: {path.parent.name}')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        backend = getattr(module, 'BACKEND', None)
        if backend is None or not all(callable(getattr(backend, method, None))
                                      for method in ('doctor', 'run', 'status')):
            raise ValueError(f'{path.parent.name}/backend.py must export BACKEND')
        if not isinstance(backend.name, str) or not isinstance(backend.version, str):
            raise ValueError('Backend name and version must be strings')
        if backend.name in found:
            raise ValueError(f'Duplicate backend name: {backend.name}')
        found[backend.name] = backend
    return found
