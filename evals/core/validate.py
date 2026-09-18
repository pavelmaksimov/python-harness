"""Validate the shared JSON schema subset and repository cross-references."""
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path

from .matrix import load_matrix, catalog_discrepancies


def _validate(value, schema: dict, path: str, errors: list[str]) -> None:
    types = {'object': dict, 'array': list, 'string': str, 'integer': int,
             'number': (int, float), 'boolean': bool, 'null': type(None)}
    expected = schema.get('type')
    if expected is not None:
        expected = expected if isinstance(expected, list) else [expected]
        valid = any(isinstance(value, types[kind]) and
                    not (kind in ('integer', 'number') and isinstance(value, bool))
                    for kind in expected)
        if not valid:
            errors.append(f'{path}: expected {expected}')
            return
    if 'const' in schema and value != schema['const']:
        errors.append(f'{path}: expected {schema["const"]!r}')
    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{path}: invalid value {value!r}')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            errors.append(f'{path}: number must be finite')
        if 'minimum' in schema and value < schema['minimum']:
            errors.append(f'{path}: below minimum')
        if 'maximum' in schema and value > schema['maximum']:
            errors.append(f'{path}: above maximum')
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0):
            errors.append(f'{path}: string too short')
        if schema.get('format') == 'date-time':
            try:
                if datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is None:
                    raise ValueError('timezone required')
            except ValueError:
                errors.append(f'{path}: expected timezone-aware ISO timestamp')
    if isinstance(value, list):
        if schema.get('uniqueItems') and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            errors.append(f'{path}: duplicate items')
        for index, item in enumerate(value):
            _validate(item, schema.get('items', {}), f'{path}[{index}]', errors)
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        for key in schema.get('required', []):
            if key not in value:
                errors.append(f'{path}.{key}: required')
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], f'{path}.{key}', errors)
            elif schema.get('additionalProperties') is False:
                errors.append(f'{path}.{key}: unknown property')
            elif isinstance(schema.get('additionalProperties'), dict):
                _validate(item, schema['additionalProperties'], f'{path}.{key}', errors)


def validate_manifest(manifest: dict, repo_root: Path | None = None) -> list[str]:
    root = repo_root or Path(__file__).resolve().parents[2]
    schema = json.loads((root / 'evals/schema/run-manifest.schema.json').read_text(encoding='utf-8'))
    errors: list[str] = []
    _validate(manifest, schema, '$', errors)
    return errors


def load_tasks(repo_root: Path) -> list[dict]:
    tasks = []
    for path in sorted((repo_root / 'evals/tasks').glob('*/task.json')):
        if path.is_symlink() or not path.resolve().is_relative_to(repo_root.resolve()):
            raise ValueError('Task manifest escapes repository')
        task = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(task, dict):
            raise ValueError(f'{path.parent.name}: task must be an object')
        task.setdefault('id', path.parent.name)
        if task['id'] != path.parent.name:
            raise ValueError(f'{path.parent.name}: task ID differs from directory')
        tasks.append(task)
    return tasks


def _task_errors(task: dict) -> list[str]:
    """The manifest shape the core actually reads; drift here fails runs at load."""
    identifier = task.get('id', '?')
    errors: list[str] = []
    prompt = task.get('prompt')
    if not (isinstance(prompt, str) and prompt.strip()) and not task.get('prompt_file'):
        errors.append(f'{identifier}: missing prompt or prompt_file')
    if 'rubric' not in task and not task.get('rubric_file'):
        errors.append(f'{identifier}: missing rubric or rubric_file')
    checks = task.get('checks', [])
    if not isinstance(checks, list):
        errors.append(f'{identifier}: checks must be a list')
        return errors
    for index, check in enumerate(checks):
        label = f"{identifier}: checks[{index}]"
        if not isinstance(check, dict) or check.get('kind') != 'shell':
            errors.append(f'{label}: only shell checks are supported')
            continue
        command = check.get('command')
        valid_command = isinstance(command, str) and command.strip() or (
            isinstance(command, list) and command and all(isinstance(arg, str) for arg in command))
        if not valid_command:
            errors.append(f'{label}: command must be a nonempty string or argument list')
        if check.get('on_fixture') not in (None, 'pass', 'fail'):
            errors.append(f'{label}: on_fixture must be "pass" or "fail"')
    return errors


def validate_repository(repo_root: Path) -> dict:
    root = repo_root.resolve()
    matrix = load_matrix(root)
    errors = list(catalog_discrepancies(root, matrix))
    tasks = load_tasks(root)
    if not tasks:
        return {'errors': errors, 'notes': ['No probes yet: evals/tasks is empty or absent.']}
    by_number = {row.number: row for row in matrix}
    coverage = Counter()
    for task in tasks:
        errors.extend(_task_errors(task))
        numbers = task.get('covered_numbers', [])
        if not isinstance(numbers, list) or any(type(n) is not int for n in numbers):
            errors.append(f'{task["id"]}: covered_numbers must contain integers')
            continue
        coverage.update(numbers)
        for number in numbers:
            if number not in by_number:
                errors.append(f'{task["id"]}: unknown covered number {number}')
                continue
            row = by_number[number]
            if not (row.general_workflow or row.future_probe or row.all_code_probes):
                probe = row.primary_probe.strip('`')
                if probe and probe != task['id']:
                    errors.append(f'{task["id"]}: number {number} belongs to {probe}')
        for item in task.get('materialize', []):
            source = item.get('from', '')
            path = root / source
            if not source or Path(source).is_absolute() or not path.resolve().is_relative_to(root) or not path.exists():
                errors.append(f'{task["id"]}: missing/unsafe materialize.from {source}')
    for number, row in by_number.items():
        if row.general_workflow or row.future_probe:
            if coverage[number]:
                errors.append(f'{row.id}: reserved for {row.primary_probe}, covered by {coverage[number]} probe(s)')
        elif row.all_code_probes:
            if coverage[number] < 1:
                errors.append(f'{row.id}: no probe covers it')
        elif coverage[number] != 1:
            errors.append(f'{row.id}: expected exactly one probe, found {coverage[number]}')
    return {'errors': errors, 'notes': []}
