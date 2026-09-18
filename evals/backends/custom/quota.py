"""Provider quota holds: an exhausted window is waited out, never retried.

The shared core names the symptom (``provider_quota``) and keeps the provider's
own words in the run's ``provider-quota.json``. This module owns the lifecycle
rule the backend derives from it: no attempt starts while the window the
provider named is still closed, and the wait itself is recorded as a verified
incident once a later run succeeds.

The hold is operational state, not knowledge: it lives in git-ignored scratch,
it is replaced whenever the provider states a newer window, and it is removed on
the run that finally succeeds. The provider's statement is kept verbatim, so a
reader never has to trust a moment this backend computed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from evals.core.artifacts import DIAGNOSTICS
from evals.core.knowledge import sanitize, validate_identifier
from evals.core.profiles import load_profile

DIRECTORY = 'memory/.tmp/evals/quota'
REMEDY = {'kind': 'quota_wait',
          'description': 'wait for the provider quota window to reset; a different judge profile is a '
                         'human decision, never a substitution'}
ROLES = ('subject', 'judge')


def _now() -> datetime:
    return datetime.now(timezone.utc)


def path(repo_root: Path, provider: str) -> Path:
    """The hold file of one provider; the provider is an identifier, never a path."""
    validate_identifier(provider)
    return Path(repo_root) / DIRECTORY / f'{provider}.json'


def read(repo_root: Path, provider: str) -> dict | None:
    try:
        record = json.loads(path(repo_root, provider).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def clear(repo_root: Path, provider: str) -> None:
    path(repo_root, provider).unlink(missing_ok=True)


def expired(hold: dict, *, now: datetime | None = None) -> bool:
    """Whether the moment the provider stated has passed.

    A hold without a readable moment never expires by itself: the backend does
    not invent a reset the provider did not state, so only a human removes it.
    """
    reset = hold.get('reset_at')
    if not isinstance(reset, str) or not reset:
        return False
    try:
        moment = datetime.fromisoformat(reset.replace('Z', '+00:00'))
    except ValueError:
        return False
    if moment.tzinfo is None:
        return False
    return (now or _now()) >= moment


def detail(hold: dict) -> str:
    """The provider's statement, readable in one line."""
    parts = [f"provider {hold.get('provider', '?')}"]
    if hold.get('role'):
        parts.append(f"({hold['role']})")
    parts.append(f"said: {str(hold.get('message', 'quota exhausted')).strip()!r}")
    reset = hold.get('reset_at')
    if isinstance(reset, str) and reset:
        parts.append(f'reset at {reset} ({hold.get("reset_timezone", "unknown")} timezone)')
    elif hold.get('reset_hint'):
        parts.append(f"reset stated as {hold['reset_hint']}, which is not a readable moment")
    else:
        parts.append('no reset moment stated')
    return '; '.join(parts)


def refusal(hold: dict) -> str:
    """Why no attempt was started, and what actually clears the hold."""
    provider = hold.get('provider', '')
    return (f'provider quota hold: {detail(hold)}. '
            f'No attempt was started; wait for the window to reset, then re-run — a different judge '
            f'profile is a human decision. Clear the hold early with '
            f'`rm {DIRECTORY}/{provider}.json` once the provider confirms the quota is back.')


def _provider(repo_root: Path, alias: str) -> str | None:
    try:
        provider = load_profile(Path(repo_root), alias).get('provider')
    except (ValueError, OSError):
        return None
    return provider if isinstance(provider, str) and provider else None


def _holds(repo_root: Path, request) -> list[tuple[str, dict]]:
    """Every hold that applies to this run, in role order, without duplicates."""
    found: list[tuple[str, dict]] = []
    for alias in (request.subject_profile, request.judge_profile):
        provider = _provider(repo_root, alias)
        if not provider or any(name == provider for name, _ in found):
            continue
        hold = read(repo_root, provider)
        if hold is not None:
            found.append((provider, hold))
    return found


def blocking(repo_root: Path, request) -> dict | None:
    """The first hold whose window is still closed: this run must not start."""
    for _, hold in _holds(repo_root, request):
        if not expired(hold):
            return hold
    return None


def releasable(repo_root: Path, request) -> dict | None:
    """The first hold whose stated reset has passed: the wait is over."""
    for _, hold in _holds(repo_root, request):
        if expired(hold):
            return hold
    return None


def release(repo_root: Path, request) -> None:
    """Drop this run's holds: a successful run proves the window is open again."""
    for provider, _ in _holds(repo_root, request):
        clear(repo_root, provider)


def observe(repo_root: Path, run_dir: Path, *, context: dict) -> dict | None:
    """Turn one core quota diagnostic into the hold a later run is governed by.

    The record is shaped like an incident, so the run that finally succeeds
    promotes it through the knowledge API instead of a second format existing
    for the same fact.
    """
    artifact = Path(run_dir) / DIAGNOSTICS['provider_quota']
    try:
        payload = json.loads(artifact.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    provider = payload.get('provider')
    if not isinstance(provider, str) or not provider:
        return None

    def text(key: str) -> str | None:
        value = payload.get(key)
        return value if isinstance(value, str) and value else None

    role = payload.get('role') if payload.get('role') in ROLES else ''
    record = {
        'provider': provider, 'role': role,
        'stage': f'custom_{role}' if role else 'custom_supervisor',
        'symptom': f'{role} provider_quota'.strip(),
        'applicability': dict(context, provider=provider),
        'remedy': dict(REMEDY),
        'message': text('provider_said') or 'the provider reported an exhausted quota',
        'reset_hint': text('reset_hint'),
        'reset_at': text('reset_at'),
        'reset_timezone': text('reset_timezone'),
        'observed_at': text('observed_at') or _now().isoformat(timespec='seconds'),
        'run_id': text('run_id') or '',
    }
    target = path(repo_root, provider)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.tmp')
    if target.is_symlink() or temporary.is_symlink():
        raise ValueError('Quota hold symlinks are forbidden')
    temporary.write_text(json.dumps(sanitize(record), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)
    return record
