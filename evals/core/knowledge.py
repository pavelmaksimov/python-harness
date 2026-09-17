"""Sanitized, deterministic knowledge records; no credentials or environment reads.

All writers take an explicit repository root and return the persisted dictionary.
Incidents require ``verification={status: 'success', run_id, succeeded_at}``.
Profiles additionally bind verification to the human-selected exact model (see
profiles.validate_profile). Backend health may describe a failure, but never
implicitly promotes an unverified remedy. INDEX is regenerated after every write.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime

_REDACTED = "[REDACTED]"
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SECRET_KEY = re.compile(
    r"(?i)(?:^|[_\W])(?:api[_-]?key|token|secret|password|passwd|authorization|"
    r"cookie|credentials?|private[_-]?key|env|environ|environment|env_contents)(?:$|[_\W])"
)
_HOME = re.compile(r"(?i)(?:/(?:home|Users)/[^\s\"'<>;,]+|/root(?:/[^\s\"'<>;,]*)?|[A-Z]:\\Users\\[^\s\"'<>;,]+)")
_ASSIGNMENT = re.compile(r"(?m)(\b[A-Z][A-Z0-9_]*\s*=\s*)(?:\"[^\"]*\"|'[^']*'|[^\s;,]+)")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|"
    r"passwd|authorization|cookie)\b[\"']?\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
_TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b")


def sanitize(value):
    """Return JSON-compatible data with secrets, env payloads and home paths removed.

    Redaction is based solely on supplied keys/text, never on local environment
    contents. Unknown unlabeled secrets cannot be identified; callers must label
    secret/env payloads rather than passing arbitrary opaque credentials as prose.
    """
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("knowledge keys must be strings")
            clean_key = sanitize(key)
            if clean_key in result:
                raise ValueError("sanitization produced duplicate keys")
            field = re.sub(r"([a-z])([A-Z])", r"\1_\2", key)
            result[clean_key] = _REDACTED if _SECRET_KEY.search(field) else sanitize(item)
        return result
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", _REDACTED, value, flags=re.S)
        value = re.sub(r"(?i)\bBearer\s+[^\s\"',;]+", "Bearer " + _REDACTED, value)
        value = re.sub(r"(https?://)[^/\s@]+@", r"\1[REDACTED]@", value)
        value = _TOKEN.sub(_REDACTED, value)
        value = _ASSIGNMENT.sub(lambda m: m[1] + _REDACTED, value)
        value = _SECRET_ASSIGNMENT.sub(lambda m: m[1] + _REDACTED, value)
        return _HOME.sub("[HOME]", value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError("knowledge values must be finite JSON data")


def validate_identifier(value: str) -> str:
    """Validate a single filename/provider/run identifier, never a path."""
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("invalid knowledge identifier")
    return value


def knowledge_path(repo_root: Path, *parts: str) -> Path:
    """Resolve a knowledge path without following any knowledge-tree symlinks."""
    path = Path(repo_root).resolve()
    for part in ("evals", "knowledge", *parts):
        validate_identifier(part)
        path = path / part
        if path.is_symlink():
            raise ValueError("knowledge symlinks are forbidden")
    return path


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _success(verification: dict) -> None:
    if not isinstance(verification, dict) or verification.get("status") != "success":
        raise ValueError("a successful verification run is required")
    validate_identifier(verification.get("run_id"))
    timestamp = verification.get("succeeded_at")
    if not isinstance(timestamp, str):
        raise ValueError("verification requires succeeded_at")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid success timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("success timestamp must include a timezone")


def fingerprint(data: dict) -> str:
    """Hash stage, whitespace-normalized sanitized symptom and applicability.

    Counts, remedy, failed attempts and verification evidence do not change an
    incident identity. Put provider/version constraints in applicability.
    """
    clean = sanitize(data)
    stage = clean.get("stage")
    symptom = clean.get("symptom")
    applicability = clean.get("applicability")
    if not isinstance(stage, str) or not stage.strip() or not isinstance(symptom, str) or not symptom.strip():
        raise ValueError("incident requires stage and symptom")
    if not isinstance(applicability, dict) or not applicability:
        raise ValueError("incident requires applicability constraints")
    identity = {"stage": stage.strip(), "symptom": " ".join(symptom.split()), "applicability": applicability}
    return hashlib.sha256(_json(identity).encode()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("knowledge symlinks are forbidden")
    # Explicit dir avoids tempfile consulting TMPDIR or other environment values.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".write-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _store(repo_root: Path, category: str, name: str, data: dict) -> dict:
    validate_identifier(name)
    clean = sanitize(data)
    path = knowledge_path(repo_root, category, name + ".json")
    _atomic_write(path, _json(clean))
    generate_index(repo_root)
    return clean


def record_incident(repo_root: Path, data: dict) -> dict:
    """Persist a verified remedy and increment occurrences for repeated incidents.

    Required: stage, symptom, applicability, failed_attempts (list), remedy
    (nonempty string/dict), verification. Optional superseded_by is a fingerprint.
    Caller-supplied fingerprints/counts are not trusted. Returns the stored record.
    """
    _success(data.get("verification"))
    remedy = data.get("remedy")
    if not isinstance(remedy, (str, dict)) or not remedy:
        raise ValueError("incident requires a verified remedy")
    if not isinstance(data.get("failed_attempts"), list):
        raise ValueError("incident requires failed_attempts")
    successor = data.get("superseded_by")
    if successor is not None and (not isinstance(successor, str) or not re.fullmatch(r"[a-f0-9]{64}", successor)):
        raise ValueError("superseded_by must be an incident fingerprint")
    identity = fingerprint(data)
    if successor == identity:
        raise ValueError("an incident cannot supersede itself")
    path = knowledge_path(repo_root, "incidents", identity + ".json")
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    record = dict(data, fingerprint=identity, occurrences=previous.get("occurrences", 0) + 1, superseded_by=successor)
    attempts = sanitize(previous.get("failed_attempts", []))
    for attempt in sanitize(data["failed_attempts"]):
        if attempt not in attempts:
            attempts.append(attempt)
    record["failed_attempts"] = attempts
    record["symptom"] = " ".join(sanitize(data["symptom"]).split())
    record["stage"] = data["stage"].strip()
    return _store(repo_root, "incidents", identity, record)


def record_provider_profile(repo_root: Path, alias: str, data: dict) -> dict:
    """Persist only a human-selected profile proven by an exact successful run."""
    from .profiles import validate_profile
    validate_profile(data)
    clean = sanitize(data)
    validate_profile(clean)
    if any(clean[key] != data[key] for key in ("provider", "model", "variant", "opencode_version")):
        raise ValueError("profile identifiers must not contain sensitive content")
    return _store(repo_root, "providers", alias, clean)


def record_backend_health(repo_root: Path, name: str, data: dict) -> dict:
    """Store sanitized backend health/version data, including unhealthy results.

    If the record includes a remedy, successful verification is mandatory.
    """
    if not isinstance(data, dict) or not data:
        raise ValueError("backend health must be a nonempty object")
    if data.get("remedy"):
        _success(data.get("verification"))
    return _store(repo_root, "backends", name, data)


def _files(repo_root: Path) -> list[Path]:
    root = knowledge_path(repo_root)
    if not root.exists():
        return []
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("knowledge symlinks are forbidden")
        if path.is_file() and not path.name.startswith(".write-"):
            files.append(path)
    return files


def generate_index(repo_root: Path) -> Path:
    """Regenerate the deterministic short index from stored JSON records."""
    root = knowledge_path(repo_root)
    lines = ["# Eval knowledge", "", "Generated by evals.core.knowledge; do not edit by hand.", ""]
    files = _files(repo_root)
    for category in ("providers", "incidents", "backends"):
        lines.extend(["## " + category.title(), ""])
        records = [path for path in files if path.parent.name == category and path.suffix == ".json"]
        if not records:
            lines.extend(["No records.", ""])
            continue
        for path in records:
            # Record labels are filenames, not free text or unsanitized metadata.
            validate_identifier(path.stem)
            lines.append(f"- [{path.stem}]({category}/{path.name})")
        lines.append("")
    destination = knowledge_path(repo_root, "INDEX.md")
    _atomic_write(destination, "\n".join(lines))
    return destination


def revision(repo_root: Path) -> str:
    """SHA-256 over sorted relative filenames and bytes, including generated INDEX.

    Missing/empty knowledge hashes to SHA-256 of empty bytes. Every regular file
    in the knowledge tree is covered; symlinks are rejected rather than followed.
    """
    root = knowledge_path(repo_root)
    digest = hashlib.sha256()
    for path in _files(repo_root):
        name = path.relative_to(root).as_posix().encode()
        content = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()
