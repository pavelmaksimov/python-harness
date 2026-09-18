"""Exact, human-selected OpenCode profiles; discovery never starts a model run.

Discover candidates, present them to a human, call select_candidate with their
explicit choice, then run an isolated smoke with that exact model/variant. Only
record_provider_profile writes the resulting verified profile. Missing profiles
and malformed catalogs fail closed; nothing is substituted at run time.

The one exception is declared, not automatic: a judge profile may name another
verified judge profile as its ``fallback``, and only the provider-quota symptom
uses it — see ``resolve_fallback``. Every run records which profile judged.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from .knowledge import _success, knowledge_path, sanitize, validate_identifier


def _model_id(value: str) -> None:
    """Model IDs are metadata, never filenames: one visible token, no traversal.

    Real catalogs include vendor/model IDs and rolling aliases such as
    ``~anthropic/claude-opus-latest``, so the shape is only bounded by length,
    invisible characters and path traversal.
    """
    if (
        not isinstance(value, str) or not 0 < len(value) <= 256
        or not re.fullmatch(r"[^\s\x00-\x1f\x7f]+", value)
        or value.startswith(("/", "."))
        or ".." in value.split("/")
    ):
        raise ValueError("invalid exact model identifier")


def validate_profile(data: dict, role: str | None = None) -> None:
    """Validate the profile and success proof, without inspecting local config.

    Required profile fields: provider, model, variant (string or null),
    friendly_name, role (subject/judge), opencode_version, metadata (object),
    verification_run_id, succeeded_at, human_selected=True and verification.
    Verification requires status='success', run_id, succeeded_at and exact
    provider/model/variant/opencode_version fields matching the profile.
    """
    if not isinstance(data, dict):
        raise ValueError("profile must be an object")
    validate_identifier(data.get("provider"))
    _model_id(data.get("model"))
    if "variant" not in data:
        raise ValueError("profile requires an explicit variant (or null)")
    if data["variant"] is not None:
        validate_identifier(data["variant"])
    if data.get("fallback") is not None:
        validate_identifier(data["fallback"])
    if data.get("role") not in {"subject", "judge"}:
        raise ValueError("profile role must be subject or judge")
    if role is not None and (role not in {"subject", "judge"} or data["role"] != role):
        raise ValueError("profile role does not match the requested role")
    for key in ("friendly_name", "opencode_version"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"profile requires {key}")
    if not isinstance(data.get("metadata"), dict):
        raise ValueError("profile requires a metadata snapshot")
    if data.get("human_selected") is not True:
        raise ValueError("human model selection is required before verification")
    verification = data.get("verification")
    _success(verification)
    if verification["run_id"] != data.get("verification_run_id") or verification["succeeded_at"] != data.get("succeeded_at"):
        raise ValueError("profile success evidence does not match verification")
    for key in ("provider", "model", "variant", "opencode_version"):
        if key not in verification or verification[key] != data[key]:
            raise ValueError(f"verification does not prove the selected {key}")


def load_profile(repo_root: Path, alias: str, role: str | None = None) -> dict:
    """Load a verified alias exactly; absence never triggers discovery or fallback."""
    validate_identifier(alias)
    path = knowledge_path(repo_root, "providers", alias + ".json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"profile {alias!r} is missing or invalid; human selection and successful smoke are required") from exc
    validate_profile(data, role)
    clean = sanitize(data)
    validate_profile(clean, role)
    if any(clean[key] != data[key] for key in ("provider", "model", "variant", "opencode_version")):
        raise ValueError("profile identifiers must not contain sensitive content")
    return clean


def resolve_fallback(repo_root: Path, profile: dict, alias: str) -> tuple[str | None, dict | None, str | None]:
    """The verified judge profile ``profile`` declares as its fallback, if usable.

    A fallback is another verified, human-selected judge profile named in the
    record itself — the same fixed pair of profiles, never a substitution chosen
    at run time. The profile must be a verified judge: an absent, self-referential
    or unverified alias is returned as a reason, so a caller keeps its primary
    outcome and reports why the declaration could not be honoured.
    """
    declared = profile.get("fallback")
    if declared is None:
        return None, None, None
    if not isinstance(declared, str) or not declared.strip():
        return None, None, "the declared judge fallback is not a profile alias"
    if declared == alias:
        return declared, None, f"the judge profile {declared!r} declares itself as its fallback"
    try:
        return declared, load_profile(repo_root, declared, role="judge"), None
    except (ValueError, OSError) as problem:
        return declared, None, f"the declared judge fallback {declared!r} is unusable: {problem}"


def discover_candidates(provider: str, query: str | None = None, limit: int = 5) -> list[dict]:
    """Return the 2–5 candidates a human should choose from; persist nothing.

    Each candidate carries exact IDs, display name, capabilities, cost and full
    sanitized metadata. The official verbose format is an ID line followed by a
    JSON object. ``query`` (case-insensitive substring of the exact ID or the
    friendly name) narrows a large catalog to what the human actually asked for;
    it is never a silent fallback — a filter that leaves fewer than two models is
    an error the caller must resolve with the human. Discovery has a 30-second
    timeout and never interprets shell input or inspects the inherited
    environment. Fewer than two models overall is an actionable error too.
    """
    validate_identifier(provider)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 2 <= limit <= 5:
        raise ValueError("present between two and five candidates to the human")
    if query is not None and (not isinstance(query, str) or not query.strip()):
        raise ValueError("invalid candidate query")
    try:
        result = subprocess.run(
            ["opencode", "models", provider, "--verbose"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("OpenCode model discovery failed; no profile was saved") from exc
    if result.returncode:
        raise ValueError("OpenCode model discovery failed: " + sanitize(result.stderr.strip())[:500])
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", result.stdout).strip()
    decoder = json.JSONDecoder()
    candidates = {}
    while text:
        identifier, separator, text = text.partition("\n")
        identifier = identifier.strip()
        if not separator or not identifier.startswith(provider + "/"):
            raise ValueError("invalid OpenCode verbose model catalog")
        model = identifier[len(provider) + 1:]
        _model_id(model)
        try:
            metadata, consumed = decoder.raw_decode(text.lstrip())
        except ValueError as exc:
            raise ValueError("invalid OpenCode model metadata") from exc
        text = text.lstrip()[consumed:].strip()
        if not isinstance(metadata, dict) or model in candidates:
            raise ValueError("invalid or duplicate model metadata")
        name = metadata.get("name", model)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("invalid model display name")
        candidates[model] = sanitize({
            "provider": provider,
            "model": model,
            "variant": None,
            "friendly_name": name,
            "capabilities": metadata.get("capabilities", {}),
            "cost": metadata.get("cost"),
            "metadata": metadata,
        })
    if len(candidates) < 2:
        raise ValueError("fewer than two models discovered; inspect provider availability with the human before proceeding")
    selected = candidates
    if query:
        needle = query.strip().lower()
        selected = {key: value for key, value in candidates.items() if needle in key.lower() or needle in value["friendly_name"].lower()}
    if len(selected) < 2:
        raise ValueError("fewer than two models match the requested query; ask the human to broaden it")
    return [selected[model] for model in sorted(selected)[:limit]]


def select_candidate(candidates: list[dict], choice: str | int, *, variant: str | None = None) -> dict:
    """Resolve an explicit human choice, without running or persisting anything.

    choice is a 1-based displayed index, exact provider/model, or an unambiguous
    friendly_name. Non-default variants must be present in the metadata snapshot.
    The result is a draft: role/version and exact success proof are still needed.
    """
    if isinstance(choice, int) and not isinstance(choice, bool):
        selected = candidates[choice - 1:choice] if 1 <= choice <= len(candidates) else []
    elif isinstance(choice, str) and choice.strip():
        selected = [item for item in candidates if choice in {item["provider"] + "/" + item["model"], item["friendly_name"]}]
    else:
        selected = []
    if len(selected) != 1:
        raise ValueError("an explicit unambiguous human model choice is required")
    data = sanitize(selected[0])
    if variant is not None:
        validate_identifier(variant)
        variants = data["metadata"].get("variants", {})
        if not isinstance(variants, dict) or variant not in variants:
            raise ValueError("the selected model does not advertise that variant")
    return dict(data, variant=variant, human_selected=True)
