"""Timeout-controlled processes and network-isolated deterministic checks."""
from dataclasses import dataclass
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

from .knowledge import sanitize
from .sandbox import IsolationError, isolated_command

# A quota window only the clock or the provider can restore, unlike a transient
# throttling answer to the same 429: retrying one wastes a whole run, retrying
# the other is exactly right. The wording decides, never the status code alone.
_QUOTA_WORDING = re.compile(r'(usage limit|quota|credit balance|out of credits)', re.I)
_QUOTA_RESET = re.compile(
    r'reset(?:s)?\s+(?:at|after)\s+'
    r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)', re.I)


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


class CommandError(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def timeout_seconds(value: object, default: float = 300) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('Timeout must be a finite positive number')
    return float(value)


def run_process(command: list[str] | tuple[str, ...], *, cwd: Path,
                timeout: float, output_limit: int = 1_000_000) -> ProcessResult:
    """No shell, environment inspection, or unbounded in-memory subprocess output."""
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            # Kill the entire group even after normal exit: no detached child work.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        stdout.seek(0)
        stderr.seek(0)
        out = stdout.read(output_limit + 1)
        err = stderr.read(output_limit + 1)
        if len(out) > output_limit or len(err) > output_limit:
            raise CommandError('output_limit', 'Process output exceeded the capture limit')
    return ProcessResult(process.returncode, out.decode('utf-8', errors='replace'),
                         err.decode('utf-8', errors='replace'),
                         round((time.monotonic() - started) * 1000), timed_out)


def run_isolated(command: list[str] | tuple[str, ...], workspace: Path, *,
                 timeout: float, role: str = 'check', readonly: bool = False) -> ProcessResult:
    try:
        result = run_process(isolated_command(command, workspace, role=role, readonly=readonly),
                             cwd=workspace, timeout=timeout)
    except FileNotFoundError as error:
        raise IsolationError('Linux bubblewrap (bwrap) is required; host execution is forbidden') from error
    if result.returncode and 'bwrap:' in result.stderr[:4000]:
        raise IsolationError('Bubblewrap could not establish isolation: ' + result.stderr[:2000])
    return result


def classify_error(text: str) -> str:
    normalized = text.lower()
    if re.search(r'(variant.{0,80}(unsupported|invalid|unknown|not found)|'
                 r'(unsupported|invalid|unknown).{0,40}variant)', normalized):
        return 'unsupported_variant'
    if re.search(r'(model.{0,80}(not found|missing|unknown|does not exist|not available)|'
                 r'(unknown|missing|invalid).{0,40}model|providermodelnotfound)', normalized):
        return 'missing_model'
    if _QUOTA_WORDING.search(text):
        return 'provider_quota'
    return 'command_failed'


def _strings(value, depth: int = 0) -> list[str]:
    """Every string inside one JSON-shaped value, outermost first."""
    if isinstance(value, str):
        return [value]
    if depth >= 4:
        return []
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child, depth + 1)]
    if isinstance(value, list):
        return [item for child in value for item in _strings(child, depth + 1)]
    return []


def _quota_sentence(text: str) -> str:
    """The provider's own sentence about the quota, not the whole error payload."""
    try:
        payload = json.loads(text)
    except ValueError:
        payload = text
    for value in _strings(payload):
        if _QUOTA_WORDING.search(value):
            return ' '.join(value.split())[:300]
    return ' '.join(text.split())[:300]


def _reset_instant(hint: str) -> tuple[str | None, str]:
    """``(aware ISO instant, how the zone was read)`` from one stated reset time."""
    normalized = hint.strip().replace(' ', 'T')
    offset = re.search(r'([+-]\d{2})(\d{2})$', normalized)
    if offset:
        normalized = normalized[:offset.start()] + offset.group(1) + ':' + offset.group(2)
    try:
        parsed = datetime.fromisoformat(normalized.replace('Z', '+00:00'))
    except ValueError:
        return None, 'unparsed'
    if parsed.tzinfo is None:
        # Zone-less provider clock: read it on the local clock, the one the
        # operator compares it against, and say so instead of assuming a zone.
        return parsed.astimezone().isoformat(timespec='seconds'), 'local'
    return parsed.isoformat(timespec='seconds'), 'stated'


def quota_hold(text: str) -> dict:
    """What an exhausted provider said: the sentence and the stated reset moment.

    ``reset_timezone`` records how the zone-less hint was read, and ``reset_at``
    stays ``None`` when the provider stated no parseable reset, so a caller never
    invents a moment the provider did not state.
    """
    hint = _QUOTA_RESET.search(text)
    reset_at, zone = _reset_instant(hint.group(1)) if hint else (None, None)
    return {'message': _quota_sentence(text), 'hint': hint.group(1) if hint else None,
            'reset_at': reset_at, 'reset_timezone': zone}


def parse_opencode(result: ProcessResult) -> tuple[str, dict]:
    """Parse JSONL events; error events are failures even when the CLI exits zero.

    OpenCode re-emits a part as it streams, each time with the accumulated text,
    so parts are keyed by ID and the last version of each part wins.
    """
    if result.timed_out:
        raise CommandError('timeout', 'OpenCode command exceeded its timeout')
    if result.returncode:
        message = (result.stderr + '\n' + result.stdout).strip()
        raise CommandError(classify_error(message), message or 'OpenCode command failed')
    parts: dict[str, dict] = {}
    order: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError) as error:
            raise CommandError('malformed_json', 'OpenCode returned malformed JSON') from error
        if not isinstance(event, dict) or not isinstance(event.get('type'), str):
            raise CommandError('malformed_json', 'OpenCode JSON must contain typed event objects')
        if event['type'] == 'error':
            message = json.dumps(event.get('error', event), ensure_ascii=False)
            raise CommandError(classify_error(message), message)
        part = event.get('part', {})
        if not isinstance(part, dict):
            raise CommandError('malformed_json', 'OpenCode event part must be an object')
        key = part.get('id')
        key = key if isinstance(key, str) else 'anonymous-' + event['type']
        if key not in parts:
            order.append(key)
        parts[key] = event
    if not parts:
        raise CommandError('malformed_json', 'OpenCode returned an empty JSON stream')
    text, metrics = [], {'input_tokens': 0, 'output_tokens': 0, 'cost': 0.0}
    for key in order:
        event = parts[key]
        part = event['part']
        if event['type'] == 'text':
            value = part.get('text', event.get('text'))
            if not isinstance(value, str):
                raise CommandError('malformed_json', 'OpenCode text event is missing text')
            text.append(value)
        if event['type'] == 'step_finish':
            tokens = part.get('tokens', {})
            if not isinstance(tokens, dict):
                raise CommandError('malformed_json', 'OpenCode tokens must be an object')
            for destination, source in (('input_tokens', 'input'), ('output_tokens', 'output')):
                value = tokens.get(source, 0)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise CommandError('malformed_json', 'Invalid token count')
                metrics[destination] += value
            cost = part.get('cost', 0)
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                raise CommandError('malformed_json', 'Invalid cost')
            metrics['cost'] += cost
    return ''.join(text), metrics


def run_checks(checks: list[dict], workspace: Path, *, default_timeout: float = 300) -> list[dict]:
    results = []
    for index, check in enumerate(checks):
        identifier = check.get('id', f'check-{index + 1}') if isinstance(check, dict) else f'check-{index + 1}'
        try:
            if not isinstance(check, dict) or check.get('kind') != 'shell':
                raise ValueError('Only shell checks are supported')
            command = check.get('command')
            if isinstance(command, str):
                command = ['/bin/sh', '-c', command]
            elif not isinstance(command, list) or not command or not all(isinstance(arg, str) for arg in command):
                raise ValueError('Shell check command must be a string or argument list')
            outcome = run_isolated(command, workspace,
                                   timeout=timeout_seconds(check.get('timeout_seconds'), default_timeout))
            evidence = (outcome.stdout + '\n' + outcome.stderr).strip()
            if outcome.timed_out:
                status, evidence = 'error', 'Check timeout.\n' + evidence
            else:
                status = 'pass' if outcome.returncode == 0 else 'fail'
                if not evidence:
                    evidence = f'Exit status: {outcome.returncode}'
        except (OSError, ValueError, IsolationError, CommandError) as error:
            status, evidence = 'error', str(error)
        results.append({'id': str(identifier), 'status': status,
                        'evidence': sanitize(evidence)[:4000]})
    return results
