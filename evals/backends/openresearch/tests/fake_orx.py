"""Install the fake ``orx`` shim on PATH for one test and audit what it recorded."""
import contextlib
import json
import os
from pathlib import Path
import shutil

SHIM_SOURCE = Path(__file__).with_name('fake_orx_shim.py')

DEFAULT_STATE = {
    'version': '0.2.4',
    'telemetry': 'off',
    'projects': [],
    'experiments': {},
    'runs': [],
    'logs': {},
    'counter': 0,
    'artifact_root': '',
    'artifact_files': {},
    'omit_marker': False,
    'run_fails': False,
}


@contextlib.contextmanager
def install(temp_root: Path, **overrides):
    """Yield the state directory with the shim at ``orx`` on PATH."""
    bin_dir = temp_root / 'orx-bin'
    state_dir = temp_root / 'orx-state'
    bin_dir.mkdir(exist_ok=True)
    state_dir.mkdir(exist_ok=True)
    shutil.copyfile(SHIM_SOURCE, bin_dir / 'orx')
    (bin_dir / 'orx').chmod(0o755)
    state = {**DEFAULT_STATE, **overrides}
    (state_dir / 'state.json').write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    saved_path = os.environ.get('PATH')
    saved_state = os.environ.get('FAKE_ORX_STATE')
    os.environ['PATH'] = f'{bin_dir}{os.pathsep}{saved_path or ""}'
    os.environ['FAKE_ORX_STATE'] = str(state_dir)
    try:
        yield state_dir
    finally:
        if saved_path is None:
            os.environ.pop('PATH', None)
        else:
            os.environ['PATH'] = saved_path
        if saved_state is None:
            os.environ.pop('FAKE_ORX_STATE', None)
        else:
            os.environ['FAKE_ORX_STATE'] = saved_state


def argv_calls(state_dir: Path) -> list[list[str]]:
    path = state_dir / 'argv.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def commands(state_dir: Path) -> list[str]:
    return [call[0] for call in argv_calls(state_dir) if call]
