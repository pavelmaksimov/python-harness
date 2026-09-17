"""The only normalized run artifact format, shared by every backend."""
import json
from pathlib import Path

from .knowledge import sanitize


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
