"""Knowledge persistence, redaction and explicit model-selection contracts."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from evals.core.knowledge import (
    fingerprint, generate_index, record_backend_health, record_incident,
    record_provider_profile, revision, sanitize,
)
from evals.core.profiles import discover_candidates, load_profile, select_candidate


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / "memory" / ".tmp" / "evals"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.incident = {
            "stage": "subject", "symptom": "Unsupported variant",
            "applicability": {"provider": "example", "opencode_version": "1.2.3"},
            "failed_attempts": [{"action": "retry unchanged", "result": "failed"}],
            "remedy": "Use the explicitly approved supported variant",
            "verification": {"status": "success", "run_id": "run-1", "succeeded_at": "2026-09-17T12:00:00Z"},
        }
        self.profile = {
            "provider": "example", "model": "vendor/exact-model", "variant": "high",
            "friendly_name": "Exact model", "role": "subject", "opencode_version": "1.2.3",
            "metadata": {"variants": {"high": {}}, "capabilities": {"reasoning": True}},
            "verification_run_id": "run-1", "succeeded_at": "2026-09-17T12:00:00Z",
            "human_selected": True,
            "verification": {
                "status": "success", "run_id": "run-1", "succeeded_at": "2026-09-17T12:00:00Z",
                "provider": "example", "model": "vendor/exact-model", "variant": "high", "opencode_version": "1.2.3",
            },
        }

    def test_fingerprint_is_stable_across_noise_but_scoped_to_applicability(self):
        first = dict(self.incident, symptom="  Failed at /" + "home/alice/project/file\n")
        second = dict(self.incident, symptom="Failed at /" + "home/bob/other/file", remedy="different remedy", occurrences=8)
        second["applicability"] = dict(reversed(list(first["applicability"].items())))
        self.assertEqual(fingerprint(first), fingerprint(second))
        second["applicability"]["opencode_version"] = "2.0.0"
        self.assertNotEqual(fingerprint(first), fingerprint(second))

    def test_recursive_redaction_does_not_mutate_input_or_consult_environment(self):
        secret = "sk-" + "syntheticCredential12345"
        home = "/" + "home/alice/private/file"
        data = {
            "nested": [{"apiKey": "opaque", "accessToken": "opaque-two", "environment": {"CUSTOM": "hidden"}}],
            "message": f"Bearer {secret} {home} CUSTOM_VALUE='private content' password=hidden",
            "url": "https://someone:password@example.invalid/path",
            "metadata": {"tokens": 500, "cost": 0.2, "enabled": True},
        }
        original = copy.deepcopy(data)
        with patch("os.getenv", side_effect=AssertionError("environment inspection")), patch.object(Path, "home", side_effect=AssertionError("home inspection")):
            result = sanitize(data)
        text = json.dumps(result)
        for private in (secret, home, "opaque", "hidden", "private content", "someone:password"):
            self.assertNotIn(private, text)
        self.assertEqual(result["metadata"], data["metadata"])
        self.assertEqual(data, original)
        self.assertEqual(sanitize(result), result)

    def test_redacts_private_keys_windows_paths_and_json_credentials(self):
        value = {
            "log": 'token="opaque-secret" ' + r"C:\Users\Alice\private" + "\n-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----",
            "env": ["CUSTOM=opaque-env"],
            "cookie": "session=opaque-cookie",
        }
        text = json.dumps(sanitize(value))
        for private in ("opaque-secret", "Alice", "private-material", "opaque-env", "opaque-cookie"):
            self.assertNotIn(private, text)
        with self.assertRaises(ValueError):
            sanitize({"not_json": float("nan")})

    def test_verified_incident_persists_and_retains_failed_paths(self):
        stored = record_incident(self.root, self.incident)
        again = dict(self.incident, failed_attempts=[{"action": "increase timeout", "result": "failed"}])
        repeated = record_incident(self.root, again)
        self.assertEqual(stored["fingerprint"], repeated["fingerprint"])
        self.assertEqual(repeated["occurrences"], 2)
        self.assertEqual(len(repeated["failed_attempts"]), 2)
        path = self.root / "evals/knowledge/incidents" / (stored["fingerprint"] + ".json")
        self.assertEqual(json.loads(path.read_text()), repeated)

    def test_failed_remedy_cannot_enter_knowledge(self):
        for status in ("failed", "timeout", None):
            with self.subTest(status=status):
                data = copy.deepcopy(self.incident)
                data["verification"]["status"] = status
                with self.assertRaises(ValueError):
                    record_incident(self.root, data)
        self.assertFalse((self.root / "evals/knowledge").exists())

    def test_index_and_revision_are_deterministic_and_cover_all_categories(self):
        self.assertEqual(revision(self.root), hashlib.sha256(b"").hexdigest())
        incident = record_incident(self.root, self.incident)
        record_provider_profile(self.root, "chosen-subject", self.profile)
        record_backend_health(self.root, "custom", {"version": "1", "status": "failed", "env": {"SECRET": "do-not-store"}})
        index = self.root / "evals/knowledge/INDEX.md"
        text = index.read_text()
        for relative in ("providers/chosen-subject.json", "backends/custom.json", f"incidents/{incident['fingerprint']}.json"):
            self.assertIn(relative, text)
        before = revision(self.root)
        generate_index(self.root)
        self.assertEqual(index.read_text(), text)
        self.assertEqual(revision(self.root), before)
        record_backend_health(self.root, "custom", {"version": "2", "status": "success"})
        self.assertNotEqual(revision(self.root), before)
        self.assertNotIn("do-not-store", (self.root / "evals/knowledge/backends/custom.json").read_text())

    def test_paths_and_symlinks_cannot_escape_knowledge(self):
        for alias in ("../escape", "/absolute", "--flag", "name/child", ""):
            with self.subTest(alias=alias), self.assertRaises(ValueError):
                record_provider_profile(self.root, alias, self.profile)
        outside = self.root / "outside"
        outside.mkdir()
        base = self.root / "evals/knowledge"
        base.mkdir(parents=True)
        (base / "providers").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            record_provider_profile(self.root, "chosen", self.profile)
        with self.assertRaises(ValueError):
            revision(self.root)
        self.assertEqual(list(outside.iterdir()), [])

    def test_backend_remedy_requires_success_even_when_health_is_writable(self):
        with self.assertRaises(ValueError):
            record_backend_health(self.root, "custom", {"status": "failed", "remedy": "retry"})
        stored = record_backend_health(self.root, "custom", {"status": "failed", "version": "1"})
        self.assertEqual(stored["status"], "failed")

    def test_profile_exact_identity_and_role_are_preserved(self):
        record_provider_profile(self.root, "chosen", self.profile)
        loaded = load_profile(self.root, "chosen", "subject")
        self.assertEqual(loaded, self.profile)
        with self.assertRaises(ValueError):
            load_profile(self.root, "chosen", "judge")
        with self.assertRaises(ValueError):
            load_profile(self.root, "missing", "subject")

    def test_profile_requires_human_choice_and_matching_success_proof(self):
        changes = [
            ("human_selected", False), ("verification_run_id", "other-run"),
            ("variant", "unsupported"), ("model", "silent-substitution"),
            ("opencode_version", "new-version"), ("succeeded_at", "2026-09-18T12:00:00Z"),
        ]
        for field, value in changes:
            with self.subTest(field=field):
                data = copy.deepcopy(self.profile)
                data[field] = value
                with self.assertRaises(ValueError):
                    record_provider_profile(self.root, "chosen", data)
        self.assertFalse((self.root / "evals/knowledge").exists())

    def test_profile_load_rejects_handwritten_unverified_record(self):
        path = self.root / "evals/knowledge/providers/unverified.json"
        path.parent.mkdir(parents=True)
        data = dict(self.profile, verification={"status": "failed"})
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            load_profile(self.root, "unverified")

    def test_discovery_presents_bounded_candidates_without_persistence(self):
        output = "\n".join(
            f"example/model-{number}\n" + json.dumps({"name": f"Model {number}", "variants": {"high": {}}, "cost": {"input": number}, "capabilities": {"reasoning": True}})
            for number in reversed(range(7))
        )
        completed = subprocess.CompletedProcess([], 0, output, "")
        with patch("evals.core.profiles.subprocess.run", return_value=completed):
            candidates = discover_candidates("example")
        self.assertEqual([item["model"] for item in candidates], [f"model-{i}" for i in range(5)])
        chosen = select_candidate(candidates, "Model 2", variant="high")
        self.assertEqual((chosen["model"], chosen["variant"]), ("model-2", "high"))
        self.assertEqual(chosen["cost"], {"input": 2})
        with self.assertRaises(ValueError):
            record_provider_profile(self.root, "draft", chosen)
        with self.assertRaises(ValueError):
            select_candidate(candidates, "")
        with self.assertRaises(ValueError):
            select_candidate(candidates, 1, variant="unadvertised")
        with self.assertRaises(ValueError):
            discover_candidates("example", limit=1)
        self.assertFalse((self.root / "evals/knowledge").exists())

    def test_discovery_accepts_real_catalog_shapes_and_human_query(self):
        # Real catalogs mix nested vendor IDs and rolling "~vendor/model-latest" aliases.
        output = "\n".join([
            "example/aion-labs/aion-2.0\n" + json.dumps({"name": "Aion 2"}),
            "example/~anthropic/claude-opus-latest\n" + json.dumps({"name": "Claude Opus Latest", "variants": {"high": {}, "medium": {}}}),
            "example/~anthropic/claude-sonnet-latest\n" + json.dumps({"name": "Claude Sonnet Latest"}),
            "example/zz-plugin\n" + json.dumps({"name": "Unrelated"}),
        ])
        with patch("evals.core.profiles.subprocess.run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            candidates = discover_candidates("example", query="latest")
        self.assertEqual([item["model"] for item in candidates], ["~anthropic/claude-opus-latest", "~anthropic/claude-sonnet-latest"])
        chosen = select_candidate(candidates, 1, variant="medium")
        self.assertEqual((chosen["model"], chosen["variant"]), ("~anthropic/claude-opus-latest", "medium"))
        with patch("evals.core.profiles.subprocess.run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            with self.assertRaises(ValueError):
                discover_candidates("example", query="zz-plugin")
            with self.assertRaises(ValueError):
                discover_candidates("example", query="   ")

    def test_discovery_fails_closed_on_missing_or_malformed_catalog(self):
        results = [
            subprocess.CompletedProcess([], 0, "example/only\n{}", ""),
            subprocess.CompletedProcess([], 0, "example/broken\nnot json", ""),
            subprocess.CompletedProcess([], 1, "", "provider unavailable"),
        ]
        for result in results:
            with self.subTest(result=result), patch("evals.core.profiles.subprocess.run", return_value=result), self.assertRaises(ValueError):
                discover_candidates("example")
        with patch("evals.core.profiles.subprocess.run", side_effect=subprocess.TimeoutExpired("opencode", 30)), self.assertRaises(ValueError):
            discover_candidates("example")


if __name__ == "__main__":
    unittest.main()
