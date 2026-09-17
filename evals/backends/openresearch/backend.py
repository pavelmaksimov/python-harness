"""OpenResearch (`orx`) orchestration backend for the shared evaluation core.

Plan B of the experiment-lab parent task: this adapter owns direction numbers,
task/profile resolution, the experiment node lifecycle (one baseline root per
probe, fingerprint-keyed child variant nodes), local run supervision through the
public ``orx`` CLI, and evidence normalization. OpenResearch owns the project,
the experiment tree, branches/worktrees, recorded commits and run logs.

Only the public CLI is used (``orx projects/exp/runs/logs``); the local
OpenResearch SQLite store is never read. Every invocation carries
``--no-telemetry`` and only ``--backend local`` compute is allowed. Dangerous
commands (``delete``, ``update``, ``login``, ``logout``, ``cancel``) are refused
outright. Project registration is a one-time human step (``orx up`` dashboard
import); when it is missing, ``doctor`` prints the exact steps and fails closed.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from evals.core.backend_api import BackendResult, RunRequest
from evals.core.execute import execute_experiment
from evals.core.knowledge import (
    record_backend_health,
    record_incident,
    sanitize,
    validate_identifier,
)
from evals.core.validate import validate_manifest

ARTIFACT_NAMES = ('manifest.json', 'result.patch', 'report.md', 'status.json')
CACHE_RELATIVE = Path('memory/.tmp/orx-project.json')
JOURNAL_RELATIVE = Path('memory/.tmp/orx-runs-journal.json')
RUNS_RELATIVE = Path('memory/.tmp/orx-runs')
LOG_BYTES = 1_000_000
WAIT_TIMEOUT_SECONDS = 2400
RUN_TIMEOUT = '30m'
EXPECTED_VERSION = '0.2.4'
MARKER_PREFIX = 'HARNESS_EVAL_ARTIFACT='
FORBIDDEN_COMMANDS = {'delete', 'update', 'login', 'logout', 'cancel'}
_VIEW_ROW = re.compile(r'^ {2}(?P<id>\S+) {2,}(?P<title>.*?)(?: \[root\])? {2,}\((?P<branch>[^()]+)\)$')
_REPO_LINE = re.compile(r'^ {2}repo:\s+(?P<repo>.+)$')
_EXP_FIELD = re.compile(r'^ {2}(id|branch|parent|command|last run|commit):\s+(?P<value>.*)$')
_LAST_RUN = re.compile(r'^(?P<run>\S+)\s+\((?P<status>[\w-]+)')
_REGISTRATION_STEPS = (
    'No local OpenResearch project resolves to this repository; registration is a '
    'one-time human step the backend will not work around:\n'
    '  1. orx up --no-agent --no-telemetry\n'
    '  2. import this repository in the dashboard: {repo}\n'
    '  3. verify with: orx projects --json'
)


class OrxError(RuntimeError):
    """A public orx CLI call failed, or the local store cannot serve this repo."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def selection_fingerprint(*, task_id: str, include, exclude, harness_ids,
                          source_commit: str, subject_profile: str,
                          judge_profile: str) -> str:
    """Stable node identity: task + selection + recorded commit + both profiles.

    The frozen run command is a pure function of these fields, so any change to
    harness, model, judge, task/rubric inputs or the command produces a new
    value and therefore a new child node.
    """
    payload = {
        'task_id': task_id,
        'include': list(include),
        'exclude': list(exclude),
        'harness_ids': list(harness_ids),
        'source_commit': source_commit,
        'subject_profile': subject_profile,
        'judge_profile': judge_profile,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()[:16]


def build_run_command(task_id: str, include, exclude, subject_profile: str,
                      judge_profile: str, fingerprint: str) -> str:
    """The frozen node run command; plan B fixes this exact shape."""
    include_text = ','.join(str(number) for number in include)
    command = (
        f'uv run python evals/orx_entrypoint.py execute'
        f' --task {task_id} --include {include_text}'
        f' --subject-profile {subject_profile} --judge-profile {judge_profile}'
        f' --selection {fingerprint}'
    )
    exclude_text = ','.join(str(number) for number in exclude)
    if exclude_text:
        command += f' --exclude {exclude_text}'
    return command


def node_description(request: RunRequest, fingerprint: str, catalog_version: str,
                     knowledge_revision: str) -> str:
    """Full machine-checkable node notes; the node title stays short."""
    include_text = ','.join(str(number) for number in request.include) or 'none'
    exclude_text = ','.join(str(number) for number in request.exclude) or 'none'
    return '\n'.join((
        'Harness-eval variant node (backend openresearch).',
        f'task: {request.task_id}',
        f'include-numbers: {include_text}',
        f'exclude-numbers: {exclude_text}',
        f'harness-ids: {",".join(request.selection.harness_ids)}',
        f'source-commit: {request.source_commit}',
        f'catalog-version: {catalog_version}',
        f'subject-profile: {request.subject_profile}',
        f'judge-profile: {request.judge_profile}',
        f'knowledge-revision: {knowledge_revision}',
        f'selection-fingerprint: {fingerprint}',
        'artifact-contract: manifest.json result.patch report.md status.json '
        f'announced via {MARKER_PREFIX.rstrip("=")}=',
    )) + '\n'


class OpenResearchBackend:
    """Adapter implementing the backend-neutral ``Backend`` protocol."""

    name = 'openresearch'
    version = ''  # detected from `orx --version` at doctor/run time

    def __init__(self, command: str = 'orx'):
        self.command = command

    # ------------------------------------------------------------------ orx CLI
    def _orx(self, args: list[str], *, timeout: float = 180,
             stdin_text: str | None = None) -> str:
        if args and args[0] in FORBIDDEN_COMMANDS:
            raise OrxError(f'orx {args[0]} is forbidden without an explicit user command')
        try:
            result = subprocess.run(
                [self.command, '--no-telemetry', *args], capture_output=True,
                text=True, timeout=timeout, input=stdin_text, check=False,
            )
        except FileNotFoundError as exc:
            raise OrxError('orx CLI not found on PATH; install OpenResearch '
                           f'{EXPECTED_VERSION}') from exc
        except subprocess.TimeoutExpired as exc:
            raise OrxError(f'orx {args[0]} timed out') from exc
        if result.returncode:
            detail = sanitize(result.stderr.strip() or result.stdout.strip())[:400]
            raise OrxError(f'orx {args[0]} failed: {detail}')
        return result.stdout

    def _git(self, repo: Path, *args: str, timeout: float = 60) -> str:
        try:
            result = subprocess.run(('git', *args), cwd=repo, capture_output=True,
                                    text=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OrxError(f'git {args[0]} failed: {exc}') from exc
        if result.returncode:
            raise OrxError(sanitize(f'git {args[0]} failed: {result.stderr.strip()}')[:400])
        return result.stdout.strip()

    def _toplevel(self) -> Path:
        return Path(self._git(Path.cwd(), 'rev-parse', '--show-toplevel'))

    def _detect_version(self) -> str:
        match = re.search(r'(\d+\.\d+\.\d+)', self._orx(['--version']))
        if not match:
            raise OrxError('cannot parse the orx version')
        self.version = match.group(1)
        return self.version

    def _ensure_telemetry_off(self) -> str:
        status = self._orx(['telemetry', 'status'])
        if 'analytics: off' in status.lower():
            return 'off'
        self._orx(['telemetry', 'off'])
        if 'analytics: off' not in self._orx(['telemetry', 'status']).lower():
            raise OrxError('unable to keep orx telemetry off')
        return 'turned off'

    # ------------------------------------------------------------------ project
    def _projects(self) -> list[dict]:
        data = json.loads(self._orx(['projects', '--json']))
        if not isinstance(data, list):
            raise OrxError('orx projects --json must return a list')
        return data

    @staticmethod
    def _cache_path(repo_root: Path) -> Path:
        return Path(repo_root) / CACHE_RELATIVE

    def _git_identity(self, path: Path) -> Path | None:
        """The repository behind a checkout, shared by its worktrees."""
        try:
            common = self._git(path, 'rev-parse', '--git-common-dir')
        except (OrxError, OSError):
            return None
        candidate = Path(common)
        if not candidate.is_absolute():
            candidate = path / candidate
        try:
            return candidate.resolve()
        except OSError:
            return None

    def _origin_url(self, path: Path) -> str | None:
        try:
            return self._git(path, 'config', '--get', 'remote.origin.url') or None
        except OrxError:
            return None

    def _project_matches(self, project: dict, repo_root: Path) -> bool:
        """A project serves this run when it is this repository, its remote, or a
        checkout cloned from it. Worktrees of one repository therefore agree."""
        path = Path(str(project.get('path', '')))
        if not path.exists():
            return False
        mine = self._git_identity(repo_root)
        if mine is not None and self._git_identity(path) == mine:
            return True
        origin = self._origin_url(path)
        if origin is None:
            return False
        if origin == self._origin_url(repo_root):
            return True
        source = Path(origin)
        if source.exists() and mine is not None and self._git_identity(source) == mine:
            return True
        return False

    def _resolve_project(self, repo_root: Path) -> dict:
        projects = self._projects()
        target = Path(repo_root).resolve()
        cache = self._cache_path(repo_root)
        try:
            cached_id = json.loads(cache.read_text(encoding='utf-8')).get('project_id')
        except (OSError, ValueError):
            cached_id = None
        for project in projects:
            if project.get('id') == cached_id and self._project_matches(project, target):
                return project  # cache hit
        for project in projects:  # cache miss/stale: resolve by repository path
            if self._project_matches(project, target):
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps({
                    'project_id': project.get('id'), 'repo_path': str(target),
                    'resolved_at': _now(),
                }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                return project
        raise OrxError(_REGISTRATION_STEPS.format(repo=target))

    # ------------------------------------------------------------------ parsing
    @staticmethod
    def _parse_project_view(text: str) -> dict:
        repo, experiments = None, {}
        for line in text.splitlines():
            repo_match = _REPO_LINE.match(line)
            if repo_match:
                repo = repo_match.group('repo').strip()
                continue
            row = _VIEW_ROW.match(line)
            if row:
                experiments[row.group('id')] = {
                    'title': row.group('title').strip(),
                    'branch': row.group('branch').strip(),
                    'root': '[root]' in line,
                }
        return {'repo': repo, 'experiments': experiments}

    @staticmethod
    def _parse_runs(text: str) -> list[dict]:
        rows = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('ID ') or set(stripped) <= {'─'}:
                continue
            cells = re.split(r'\s{2,}', stripped)
            if len(cells) >= 2 and re.fullmatch(r'[\w.-]+', cells[0]):
                rows.append({'id': cells[0], 'status': cells[1].lower(),
                             'experiment': cells[2] if len(cells) > 2 else ''})
        return rows

    @staticmethod
    def _parse_exp_status(text: str) -> dict:
        info = {}
        lines = text.splitlines()
        if lines:
            state = re.search(r'\(([\w-]+)\)', lines[0])
            if state:
                info['state'] = state.group(1)
        for line in lines[1:]:
            field = _EXP_FIELD.match(line)
            if field:
                info[field.group(1).replace(' ', '_')] = field.group('value').strip()
        if info.get('last_run'):
            match = _LAST_RUN.match(info['last_run'])
            if match:
                info['last_run_id'] = match.group('run')
                info['last_run_status'] = match.group('status')
        return info

    @staticmethod
    def _marker_path(log: str) -> Path | None:
        found = None
        for line in log.splitlines():
            if line.startswith(MARKER_PREFIX) and line[len(MARKER_PREFIX):].strip():
                found = Path(line[len(MARKER_PREFIX):].strip())
        return found

    # ------------------------------------------------------------------- nodes
    def _view(self, project_id: str) -> dict:
        return self._parse_project_view(self._orx(['project', 'view', project_id]))

    def _create_node(self, project_id: str, *, title: str, baseline: bool = False,
                     parent: str | None = None,
                     run_command: str | None = None) -> str:
        before = set(self._view(project_id)['experiments'])
        args = ['create-experiment', project_id, '--title', title]
        if baseline:
            args.append('--baseline')
        elif parent:
            args += ['--parent', parent]
        if run_command:
            args += ['--run-command', run_command]
        self._orx(args)
        created = sorted(set(self._view(project_id)['experiments']) - before)
        if len(created) != 1:
            raise OrxError('cannot identify the experiment node just created')
        return created[0]

    def _desc(self, experiment_id: str) -> str:
        return self._orx(['exp', 'desc', experiment_id]).strip()

    def _set_desc(self, experiment_id: str, text: str) -> None:
        self._orx(['exp', 'desc', experiment_id, '--stdin'], stdin_text=text)

    def _ensure_baseline(self, project_id: str, task_id: str) -> dict:
        title = f'eval {task_id}'
        view = self._view(project_id)
        for node_id, node in view['experiments'].items():
            if node['root'] and node['title'] == title:
                return {'id': node_id, 'created': False, **node}
        created = self._create_node(project_id, title=title, baseline=True)
        self._set_desc(created, f'Baseline lineage root for task {task_id} '
                                '(backend openresearch).\n')
        return {'id': created, 'created': True,
                **self._view(project_id)['experiments'][created]}

    def _ensure_variant(self, project_id: str, baseline: dict, request: RunRequest,
                        fingerprint: str, run_command: str, description: str) -> tuple[str, dict, bool]:
        for node_id, node in self._view(project_id)['experiments'].items():
            if node['root']:
                continue
            if re.search(rf'^selection-fingerprint: {re.escape(fingerprint)}$',
                         self._desc(node_id), re.M):
                return node_id, node, True
        created = self._create_node(
            project_id, title=f'eval {request.task_id} {fingerprint}',
            parent=baseline['id'], run_command=run_command,
        )
        self._set_desc(created, description)
        return created, self._view(project_id)['experiments'][created], False

    def _push_node_code(self, request: RunRequest, project_path: str,
                        branch: str) -> None:
        """Freeze the recorded commit onto a freshly created provisional branch.

        The push runs in the checkout that owns ``source_commit`` and targets the
        project repository. The node was created seconds ago and never ran, so
        replacing its branch is not an edit of answered evidence. A branch
        checked out in a session worktree would refuse the push; that refusal is
        surfaced, never bypassed.
        """
        self._git(Path(request.repo_root), 'push', '--force', str(project_path),
                  f'{request.source_commit}:refs/heads/{branch}')

    # --------------------------------------------------------------------- run
    def doctor(self, *, repair: bool = False) -> dict:
        report: dict = {'name': self.name, 'status': 'success', 'checks': {}}
        try:
            toplevel = self._toplevel()
        except OrxError:
            toplevel = Path.cwd().resolve()
        try:
            version = self._detect_version()
            report['checks']['version'] = {'status': 'ok', 'version': version,
                                           'expected': EXPECTED_VERSION}
        except OrxError as exc:
            report['status'] = 'blocked'
            report['checks']['version'] = {
                'status': 'error', 'error': str(exc),
                'steps': [f'install OpenResearch {EXPECTED_VERSION} and verify: orx --version'],
            }
            return report
        try:
            report['checks']['telemetry'] = {'status': 'ok',
                                             'value': self._ensure_telemetry_off()}
        except OrxError as exc:
            report['status'] = 'blocked'
            report['checks']['telemetry'] = {'status': 'error', 'error': str(exc),
                                             'steps': ['orx telemetry off']}
            return report
        try:
            project = self._resolve_project(toplevel)
            report['checks']['project'] = {'status': 'ok', 'id': project.get('id'),
                                           'path': project.get('path')}
        except OrxError as exc:
            report['status'] = 'blocked'
            report['checks']['project'] = {'status': 'error', 'steps': str(exc).splitlines()}
            return report
        health_path = toplevel / 'evals/knowledge/backends/openresearch.json'
        if not repair:
            smoke = {'status': 'not run this time; use doctor --repair'}
            try:
                smoke = json.loads(health_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
            report['checks']['smoke'] = smoke
            return report
        try:
            smoke = self._smoke(toplevel, project)
            record_backend_health(toplevel, self.name, {
                'orx_version': self.version, 'telemetry': 'off',
                'smoke': {'status': 'success', **smoke}, 'checked_at': _now(),
                'verification': {'status': 'success', 'run_id': smoke['run_id'],
                                 'succeeded_at': _now()},
            })
            report['checks']['smoke'] = {'status': 'ok', **smoke}
        except OrxError as exc:
            record_backend_health(toplevel, self.name, {
                'orx_version': self.version, 'smoke': {'status': 'error'},
                'checked_at': _now(), 'error': str(exc),
            })
            report['status'] = 'blocked'
            report['checks']['smoke'] = {'status': 'error', 'error': str(exc)}
        return report

    def _smoke(self, repo_root: Path, project: dict) -> dict:
        """Cheap marker node: prove artifacts survive a completed local run."""
        title = f'eval doctor smoke {self.version}'
        view = self._view(project['id'])
        node_id = next((node for node, data in view['experiments'].items()
                        if data['title'] == title), None)
        if node_id is None:
            command = (
                "python3 -c \"import pathlib; p=pathlib.Path('memory/.tmp/orx-smoke'); "
                "p.mkdir(parents=True, exist_ok=True); "
                "(p/'marker.txt').write_text('ok'); "
                "print('HARNESS_EVAL_ARTIFACT=' + str(p.resolve()))\""
            )
            node_id = self._create_node(project['id'], title=title, baseline=True,
                                        run_command=command)
            self._set_desc(node_id, f'Backend doctor smoke for orx {self.version}.\n')
        self._orx(['exp', 'run', node_id, '--backend', 'local',
                   '--timeout', '5m'], timeout=300)
        self._orx(['exp', 'wait', node_id, '--timeout', '900'], timeout=960)
        runs = self._parse_runs(self._orx(['runs', project['id'],
                                           '--experiment', node_id]))
        if not runs:
            raise OrxError('doctor smoke produced no run')
        run_id = runs[0]['id']
        if runs[0]['status'] != 'done':
            raise OrxError(f'doctor smoke run {run_id} is {runs[0]["status"]}')
        marker = self._marker_path(self._orx(['logs', run_id, '--bytes', str(LOG_BYTES)]))
        directory = marker if marker is not None and marker.is_dir() else \
            marker.parent if marker is not None else None
        if directory is None or not (directory / 'marker.txt').is_file():
            raise OrxError('marker artifact did not survive the smoke run; '
                           'file retrieval needs verification on this orx version')
        if (directory / 'marker.txt').read_text(encoding='utf-8') != 'ok':
            raise OrxError('smoke marker content is wrong')
        return {'run_id': run_id, 'experiment': node_id, 'marker': True}

    def _journal_path(self, repo_root: Path) -> Path:
        return Path(repo_root) / JOURNAL_RELATIVE

    def _journal(self, repo_root: Path) -> dict:
        try:
            return json.loads(self._journal_path(repo_root).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _known_incidents(self, repo_root: Path) -> list[dict]:
        directory = Path(repo_root) / 'evals/knowledge/incidents'
        if not directory.is_dir():
            return []
        records = []
        for path in sorted(directory.glob('*.json')):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if str(data.get('stage', '')).startswith('orx_'):
                records.append(data)
        return records

    def run(self, request: RunRequest) -> BackendResult:
        repo_root = Path(request.repo_root)
        started = time.monotonic()
        attempts: list[dict] = []

        def record(action: str, result: str) -> None:
            attempts.append({'action': action, 'result': result,
                             'duration_ms': round((time.monotonic() - started) * 1000),
                             'incident': None})

        self._detect_version()
        telemetry = self._ensure_telemetry_off()
        project = self._resolve_project(repo_root)
        fingerprint = selection_fingerprint(
            task_id=request.task_id, include=request.include, exclude=request.exclude,
            harness_ids=request.selection.harness_ids,
            source_commit=request.source_commit, subject_profile=request.subject_profile,
            judge_profile=request.judge_profile,
        )
        command = build_run_command(request.task_id, request.include, request.exclude,
                                    request.subject_profile, request.judge_profile,
                                    fingerprint)
        incidents = self._known_incidents(repo_root)
        record('orx resolve-project',
               f"{project.get('id')}; telemetry {telemetry}; "
               f"known orx incidents: {len(incidents)}")

        baseline = self._ensure_baseline(project['id'], request.task_id)
        description = node_description(request, fingerprint,
                                       self._catalog_version(repo_root),
                                       request.knowledge_revision)
        node_id, node, reused = self._ensure_variant(
            project['id'], baseline, request, fingerprint, command, description)
        record('orx resolve-node',
               f'{node_id} ({"reused" if reused else "created"})')
        if not reused:
            self._push_node_code(request, project.get('path', ''), node['branch'])
            record('orx push-node-code', node['branch'])

        self._orx(['exp', 'run', node_id, '--backend', 'local',
                   '--timeout', RUN_TIMEOUT], timeout=300)
        record('orx exp run', f'{node_id} backend local timeout {RUN_TIMEOUT}')
        self._orx(['exp', 'wait', node_id, '--timeout', str(WAIT_TIMEOUT_SECONDS)],
                  timeout=WAIT_TIMEOUT_SECONDS + 120)
        record('orx exp wait', node_id)
        rows = self._parse_runs(self._orx(['runs', project['id'],
                                           '--experiment', node_id]))
        if not rows:
            raise OrxError(f'no run recorded for experiment {node_id}')
        orx_run = rows[0]
        record('orx runs', f"{orx_run['id']} {orx_run['status']}")

        journal = self._journal(repo_root)
        journal[orx_run['id']] = {'project': project.get('id'), 'experiment': node_id,
                                  'fingerprint': fingerprint,
                                  'artifact_dir': str(request.workdir)}
        self._journal_path(repo_root).parent.mkdir(parents=True, exist_ok=True)
        self._journal_path(repo_root).write_text(
            json.dumps(journal, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
            encoding='utf-8')

        log = self._orx(['logs', orx_run['id'], '--bytes', str(LOG_BYTES)])
        source = self._artifact_from_marker(log, fingerprint)
        retrieval = 'log marker'
        if source is None:
            source = self._scan_for_artifacts(project.get('path', ''), node['branch'],
                                              request.task_id, fingerprint)
            retrieval = 'worktree scan'
        record('orx artifact-retrieval', f'{retrieval} for {orx_run["id"]}')
        if source is None:
            return BackendResult(
                orx_run['id'], 'error', Path(request.workdir), None, attempts,
                f'run {orx_run["id"]} is {orx_run["status"]} but its normalized '
                'artifacts could not be retrieved from the log or orx worktrees')
        if orx_run['status'] not in ('done', 'success'):
            return BackendResult(
                orx_run['id'], 'error', Path(request.workdir),
                Path(request.workdir) / 'manifest.json', attempts,
                f'orx run {orx_run["id"]} finished as {orx_run["status"]}')
        if retrieval == 'worktree scan' and orx_run['status'] == 'done':
            self._record_retrieval_incident(repo_root, orx_run['id'])
        manifest = self._export(source, request, fingerprint, project, node_id,
                                orx_run['id'], attempts)
        errors = validate_manifest(manifest, repo_root)
        if errors:
            return BackendResult(orx_run['id'], 'error', Path(request.workdir),
                                 Path(request.workdir) / 'manifest.json',
                                 manifest['attempts'],
                                 'invalid manifest: ' + '; '.join(errors))
        return BackendResult(orx_run['id'], manifest['status'], Path(request.workdir),
                             Path(request.workdir) / 'manifest.json',
                             manifest['attempts'], None)

    @staticmethod
    def _catalog_version(repo_root: Path) -> str:
        try:
            return (Path(repo_root) / 'VERSION').read_text(encoding='utf-8').strip()
        except OSError:
            return ''

    def _artifact_from_marker(self, log: str, fingerprint: str) -> Path | None:
        """Trust only a marker whose directory holds a manifest with our fingerprint.

        The log mixes subject output with entrypoint output, so a printed marker
        is evidence only when the pointed directory carries the expected manifest.
        """
        marker = self._marker_path(log)
        if marker is None:
            return None
        directory = marker if marker.is_dir() else marker.parent
        try:
            manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
            if manifest.get('backend', {}).get('ids', {}).get('fingerprint') == fingerprint:
                return directory
        except (OSError, ValueError):
            pass
        return None

    def _scan_for_artifacts(self, project_path: str, branch: str, task_id: str,
                            fingerprint: str) -> Path | None:
        """Exporter fallback: locate the entrypoint output inside orx worktrees."""
        roots: list[Path] = []
        try:
            text = self._git(Path(project_path), 'worktree', 'list', '--porcelain')
        except OrxError:
            text = ''
        current = None
        for line in text.splitlines():
            if line.startswith('worktree '):
                current = Path(line[len('worktree '):])
                roots.append(current)
            elif line.startswith('branch refs/heads/') and current is not \
                    None and line.split('refs/heads/', 1)[1] == branch:
                roots.insert(0, roots.pop(roots.index(current)))  # branch match first
        if project_path:
            roots.append(Path(project_path))
        seen = set()
        for root in roots:
            resolved = root.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            base = resolved / RUNS_RELATIVE / task_id
            if not base.is_dir():
                continue
            for manifest_path in sorted(base.glob('*/manifest.json'),
                                        key=lambda path: path.stat().st_mtime,
                                        reverse=True):
                try:
                    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    continue
                if manifest.get('backend', {}).get('ids', {}).get('fingerprint') == fingerprint:
                    return manifest_path.parent
        return None

    def _record_retrieval_incident(self, repo_root: Path, run_id: str) -> None:
        try:
            validate_identifier(run_id)
            record_incident(repo_root, {
                'stage': 'orx_artifact_retrieval',
                'symptom': 'orx logs for the finished run carry no '
                           f'{MARKER_PREFIX.rstrip("=")} marker',
                'applicability': {'backend': self.name, 'orx_version': self.version},
                'failed_attempts': [{'action': 'parse log marker', 'result': 'missing'}],
                'remedy': 'scan orx worktrees and the project repository for '
                          f'{RUNS_RELATIVE.as_posix()}/<task>/<run>/ and export from there',
                'verification': {'status': 'success', 'run_id': run_id,
                                 'succeeded_at': _now()},
            })
        except ValueError:
            pass  # evidence must stay clean; a malformed run id is not recordable

    def _export(self, source: Path, request: RunRequest, fingerprint: str,
                project: dict, node_id: str, orx_run_id: str,
                backend_attempts: list[dict]) -> dict:
        """Exporter: the only path normalized artifacts take into evals/history."""
        target = Path(request.workdir)
        target.mkdir(parents=True, exist_ok=True)
        for name in ARTIFACT_NAMES:
            shutil.copyfile(source / name, target / name)
        manifest = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
        manifest['run_id'] = orx_run_id
        manifest['backend'] = {'name': self.name, 'version': self.version,
                               'ids': {'project': project.get('id'),
                                       'experiment': node_id, 'run': orx_run_id,
                                       'fingerprint': fingerprint}}
        manifest['attempts'] = [*manifest.get('attempts', []), *backend_attempts]
        payload = sanitize(manifest)
        (target / 'manifest.json').write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        status = json.loads((target / 'status.json').read_text(encoding='utf-8'))
        status['run_id'] = orx_run_id
        (target / 'status.json').write_text(
            json.dumps(sanitize(status), ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8')
        return payload

    # ------------------------------------------------------------------ status
    def status(self, run_id: str) -> dict:
        try:
            toplevel = self._toplevel()
        except OrxError:
            return {'run_id': run_id, 'status': 'unknown'}
        entry = self._journal(toplevel).get(run_id)
        if not entry:
            return {'run_id': run_id, 'status': 'unknown'}
        info = self._parse_exp_status(self._orx(['exp', 'status', entry['experiment']]))
        return {'run_id': run_id, 'status': info.get('last_run_status', 'unknown'),
                'project': entry.get('project'), 'experiment': entry.get('experiment'),
                'fingerprint': entry.get('fingerprint'),
                'artifact_dir': entry.get('artifact_dir')}


BACKEND = OpenResearchBackend()
