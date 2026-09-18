"""The only normalized run artifact format, shared by every backend."""
import json
from pathlib import Path
import re

from .knowledge import sanitize

# The terminal set every finished run ends with, plus the diagnostics a run
# writes while it is still going: the evidence a later reader judges it by.
ARTIFACTS = {'patch': 'result.patch', 'report': 'report.md', 'status': 'status.json'}
DIAGNOSTICS = {'judge_response': 'judge-response.txt', 'provider_quota': 'provider-quota.json'}
_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z')


def declared(directory: Path) -> dict:
    """The artifact map of a run directory: the terminal set plus written diagnostics."""
    directory = Path(directory)
    found = dict(ARTIFACTS)
    found.update({key: name for key, name in DIAGNOSTICS.items() if (directory / name).is_file()})
    return found


def write_diagnostic(directory: Path, name: str, text: str) -> Path:
    """Write one sanitized diagnostic artifact atomically, at any point in a run.

    Diagnostics land while the run is still in flight, so they survive an attempt
    killed before its terminal artifacts. They never carry the completeness
    marker: ``status.json`` stays the last terminal write.
    """
    if not _NAME.fullmatch(name) or name in ARTIFACTS.values():
        raise ValueError('A diagnostic needs a safe name outside the terminal artifact set')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    temporary = directory / (name + '.tmp')
    if target.is_symlink() or temporary.is_symlink():
        raise ValueError('Artifact symlinks are forbidden')
    temporary.write_text(sanitize(text), encoding='utf-8')
    temporary.replace(target)
    return target


def read_manifest(run_dir: Path) -> dict:
    path = Path(run_dir)
    if path.is_dir():
        path /= 'manifest.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Manifest must be an object')
    return data


def write_artifacts(artifact_dir: Path, manifest: dict, patch: str, report: str) -> None:
    """Write terminal status last; it is the artifact-completeness marker.

    ``result.patch`` is written verbatim: it is the reproduction of the run, and
    rewriting its hunks would make the patch unapplicable. It is generated from
    two paths inside the run directory, so it carries workspace-relative names.
    Everything else is sanitized before it reaches disk.
    """
    directory = Path(artifact_dir)
    directory.mkdir(parents=True, exist_ok=True)
    # The manifest names its artifacts: diagnostics found on disk are added, and a
    # value the caller stated is never overridden — a wrong claim stays visible to
    # the reader instead of being silently corrected here.
    stated = manifest.get('artifacts') if isinstance(manifest.get('artifacts'), dict) else {}
    manifest = {**manifest, 'artifacts': {**declared(directory), **stated}}
    payloads = {
        'manifest.json': json.dumps(sanitize(manifest), ensure_ascii=False, indent=2) + '\n',
        'result.patch': patch,
        'report.md': sanitize(report),
        'status.json': json.dumps(sanitize({
            'run_id': manifest['run_id'], 'status': manifest['status'],
            'finished_at': manifest['finished_at'],
        }), ensure_ascii=False, indent=2) + '\n',
    }
    for name, content in payloads.items():
        target = directory / name
        if target.is_symlink():
            raise ValueError('Artifact symlinks are forbidden')
        temporary = directory / (name + '.tmp')
        if temporary.is_symlink():
            raise ValueError('Artifact symlinks are forbidden')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(target)
    # Raw path: this is the operator's handle to the run directory on this host,
    # never a committed value, so home-directory redaction does not apply.
    print(f'HARNESS_EVAL_ARTIFACT={directory}')
