"""Selection contracts independent of task/backend implementations."""

from pathlib import Path
import tempfile
import unittest

from evals.core.matrix import catalog_discrepancies, catalog_ids, load_matrix, parse_matrix
from evals.core.selection import ensure_coverage, format_selection, resolve_selection


ROOT = Path(__file__).resolve().parents[2]


class MatrixTests(unittest.TestCase):
    def test_catalog_ids_match_canonical_matrix(self):
        matrix = load_matrix(ROOT)
        self.assertEqual(set(catalog_ids(ROOT)), {item.id for item in matrix})
        self.assertEqual(catalog_discrepancies(ROOT, matrix), [])
        self.assertEqual(tuple(item.number for item in matrix), tuple(range(1, 34)))

    def test_required_advisory_and_conditional_dependencies_are_distinct(self):
        items = {item.id: item for item in load_matrix(ROOT)}
        self.assertEqual(items["python-tests"].companions, (11, 12, 30))
        self.assertEqual(items["python-sqlalchemy"].companions, (18, 19, 20))
        self.assertEqual(items["python-polyfactory"].companions, (10,))
        self.assertIn("17 и 19", items["python-polyfactory"].constraints)
        self.assertEqual(items["python-redis"].companions, ())
        self.assertEqual(items["python-architecture"].companions, ())
        self.assertEqual(items["python-monitoring"].companions, ())
        self.assertEqual(items["layers-linter"].companions, ())
        self.assertEqual(items["di-linter"].companions, (6,))

    def test_dependencies_are_read_from_rows_not_a_numeric_registry(self):
        matrix = parse_matrix(
            "| № | Harness ID | Band | Description | Constraints | Probe |\n"
            "|---:|---|---|---|---|---|\n"
            "| 1 | `example` | core | Example | Требует 2 | `example-probe` |\n"
            "| 2 | `helper` | core | Helper | Базовый core | Общий workflow |\n"
        )
        selection = resolve_selection("1", "", matrix)
        self.assertEqual(selection.harness_ids, ("example", "helper"))
        self.assertEqual(matrix[0].primary_probe, "example-probe")

    def test_malformed_table_or_dangling_dependency_is_rejected(self):
        header = "| № | Harness ID | Band | Description | Constraints | Probe |\n"
        for row in (
            "| 1 | `one` | core | Example | Требует 2 | `probe` |",
            "| 2 | `two` | core | Example | None | `probe` |",
            "| 1 | `one` | core | Example | Требует неизвестное | `probe` |",
            "| 1 | `one` | core | Example |",
            "| not-a-number | `one` | core | Example | None | `probe` |",
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                parse_matrix(header + row)

    def test_catalog_drift_is_reported_without_changing_sources(self):
        scratch = ROOT / "memory/.tmp/evals"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            repo = Path(directory)
            catalog = repo / "README.md"
            original = "## Catalog\n\n| `new-catalog-id` | New |\n\n## Other\n| `not-catalog` | Other |\n"
            catalog.write_text(original, encoding="utf-8")
            errors = catalog_discrepancies(repo, load_matrix(ROOT))
            self.assertEqual(len(errors), 2)
            self.assertIn("conventional-commits", errors[0])
            self.assertEqual(errors[1], "README Catalog IDs missing from matrix: new-catalog-id")
            self.assertEqual(catalog.read_text(encoding="utf-8"), original)


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = load_matrix(ROOT)

    def test_cli_example_preserves_original_numbers_and_expanded_ids(self):
        selection = resolve_selection("1-6,25-26", "2", self.matrix)
        self.assertEqual(selection.include_numbers, (1, 2, 3, 4, 5, 6, 25, 26))
        self.assertEqual(selection.exclude_numbers, (2,))
        self.assertEqual(selection.numbers, (1, 3, 4, 5, 6, 25, 26))
        self.assertEqual(selection.harness_ids, (
            "conventional-commits", "python-tooling", "python-workflow",
            "python-libs", "python-architecture", "python-typer", "cli-design",
        ))
        line = format_selection(selection)
        self.assertNotIn("\n", line)
        self.assertIn("1,2,3,4,5,6,25,26", line)
        self.assertTrue(all(identifier in line for identifier in selection.harness_ids))

    def test_russian_and_english_expressions_are_equivalent(self):
        russian = resolve_selection("включи 1–6 и 25—26 кроме 2 исключи 32", "", self.matrix)
        english = resolve_selection("include 1-6 and 25-26 except 2 exclude 32", (), self.matrix)
        explicit = resolve_selection((26, 25, 6, 5, 4, 3, 2, 1, 1), (32, 2), self.matrix)
        self.assertEqual(russian, english)
        self.assertEqual(english, explicit)

    def test_all_except_keeps_optional_harnesses_unless_excluded(self):
        selection = resolve_selection("всё кроме 2 и 32", "", self.matrix)
        self.assertEqual(selection.numbers, tuple(number for number in range(1, 34) if number not in (2, 32)))
        self.assertEqual(selection, resolve_selection("all except 2,32", (), self.matrix))

    def test_standard_all_does_not_implicitly_enable_optional_entries(self):
        selection = resolve_selection("всё стандартное", "", self.matrix)
        optional = {item.number for item in self.matrix if "optional" in item.band.split()}
        self.assertFalse(set(selection.numbers) & optional)
        self.assertEqual(selection, resolve_selection("all standard", (), self.matrix))
        enabled = resolve_selection("all standard,31", "", self.matrix)
        self.assertIn(31, enabled.numbers)

    def test_closure_is_transitive_across_tests_database_and_cli(self):
        self.assertEqual(resolve_selection("12", "", self.matrix).numbers, (10, 11, 12, 30))
        self.assertEqual(resolve_selection("19", "", self.matrix).numbers, (17, 18, 19, 20))
        self.assertEqual(resolve_selection("26", "", self.matrix).numbers, (25, 26))
        self.assertEqual(resolve_selection("7", "", self.matrix).numbers, (5, 6, 7))

    def test_conditional_companions_do_not_activate_without_the_condition(self):
        self.assertEqual(resolve_selection("22", "", self.matrix).numbers, (22,))
        self.assertEqual(resolve_selection("12", "17,19", self.matrix).numbers, (10, 11, 12, 30))
        self.assertEqual(resolve_selection("6", "28,29", self.matrix).numbers, (6,))

    def test_excluded_required_companion_explains_dependency(self):
        with self.assertRaisesRegex(ValueError, r"26 \(cli-design\).*25 \(python-typer\).*excluded"):
            resolve_selection("26", "25", self.matrix)
        with self.assertRaisesRegex(ValueError, "python-tests.*patch-linter"):
            resolve_selection("12", "30", self.matrix)

    def test_exclusions_are_applied_after_closure(self):
        selection = resolve_selection("7", "7", self.matrix)
        self.assertEqual(selection.numbers, (5, 6))
        self.assertEqual(selection.include_numbers, (7,))

    def test_invalid_and_empty_input_fails_without_silent_token_loss(self):
        for include in ("", "0", "34", "6-1", "1-999999999999", "1 potato 3", "all except", (True,)):
            with self.subTest(include=include), self.assertRaises(ValueError):
                resolve_selection(include, "", self.matrix)
        with self.assertRaises(ValueError):
            resolve_selection("1", "1", self.matrix)
        with self.assertRaises(ValueError):
            resolve_selection("1", "except", self.matrix)


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = load_matrix(ROOT)

    def test_general_workflow_alone_needs_no_task(self):
        ensure_coverage(resolve_selection("1,2,4", "", self.matrix), [], self.matrix)

    def test_task_declared_intersection_enables_selection(self):
        selection = resolve_selection("1-6,25-26", "2", self.matrix)
        ensure_coverage(selection, [{"id": "orders-cli", "covered_numbers": [25, 26]}], self.matrix)

    def test_dependency_can_be_covered_by_task(self):
        selection = resolve_selection("26", "", self.matrix)
        ensure_coverage(selection, [{"covered_numbers": [25]}], self.matrix)

    def test_absent_or_unrelated_probe_blocks_with_actionable_ids(self):
        selection = resolve_selection("1,25", "", self.matrix)
        for tasks in ([], [{"covered_numbers": [17, 18, 19, 20]}], [{"covered_numbers": [1]}]):
            with self.subTest(tasks=tasks), self.assertRaisesRegex(ValueError, "python-typer.*separate bounded task"):
                ensure_coverage(selection, tasks, self.matrix)

    def test_future_only_request_cannot_borrow_coverage_from_its_companions(self):
        tasks = [{"covered_numbers": list(range(1, 34))}]
        for include in ("13", "15", "21", "27", "13,15,21,27", "1,2,4,15"):
            with self.subTest(include=include), self.assertRaisesRegex(ValueError, "separate bounded task"):
                ensure_coverage(resolve_selection(include, "", self.matrix), tasks, self.matrix)

    def test_general_root_with_uncovered_companion_still_blocks(self):
        selection = resolve_selection("1,10", "", self.matrix)
        self.assertEqual(selection.include_numbers, (1, 10))
        with self.assertRaisesRegex(ValueError, "python-tests"):
            ensure_coverage(selection, [{"covered_numbers": [1, 2, 4]}], self.matrix)
        ensure_coverage(selection, [{"covered_numbers": [10]}], self.matrix)

    def test_task_coverage_rejects_unknown_numbers_and_noninteger_values(self):
        selection = resolve_selection("25", "", self.matrix)
        for numbers in ([34], [True], ["25"], "25"):
            with self.subTest(numbers=numbers), self.assertRaises(ValueError):
                ensure_coverage(selection, [{"covered_numbers": numbers}], self.matrix)
