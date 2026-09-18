"""Read public harness numbers and dependencies from the canonical Markdown table."""

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class Harness:
    number: int
    id: str
    band: str
    companions: tuple[int, ...]
    constraints: str
    primary_probe: str
    description: str = ""

    @property
    def general_workflow(self) -> bool:
        return self.primary_probe == "Общий workflow"

    @property
    def future_probe(self) -> bool:
        return self.primary_probe.startswith("Будущая ")

    @property
    def all_code_probes(self) -> bool:
        return self.primary_probe == "Все кодовые пробы"


_REQUIRED = re.compile(
    r"^(?:Использует|Требует|Автоматически добавляет|DB bundle:)\s+"
    r"(?P<numbers>\d+(?:(?:\s*,\s*|\s+и\s+)\d+)*)$",
    re.IGNORECASE,
)


def parse_matrix(text: str) -> tuple[Harness, ...]:
    """Parse six-column rows; advisory/conditional clauses are not hard edges.

    In particular, ORM-only factories do not select a database, Redis does not
    select tests by itself, and usual/standard pairings remain recommendations.
    Their full prose is retained in constraints for the task materializer.
    """
    harnesses = []
    references = set()
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("| № |"):
            if in_table or harnesses:
                raise ValueError("Multiple harness matrix tables")
            in_table = True
            continue
        if not in_table:
            continue
        if not stripped.startswith("|"):
            in_table = False
            continue
        if re.fullmatch(r"[|:\-\s]+", stripped):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 6 or not cells[0].isascii() or not cells[0].isdigit():
            raise ValueError(f"Malformed harness matrix row: {stripped}")
        number = int(cells[0])
        if number != len(harnesses) + 1:
            raise ValueError("Harness numbers must be consecutive, starting at 1")
        identifier = cells[1].strip("`")
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", identifier):
            raise ValueError(f"Invalid harness ID: {identifier}")
        if any(item.id == identifier for item in harnesses):
            raise ValueError(f"Duplicate harness ID: {identifier}")
        companions = set()
        for clause in cells[4].split(";"):
            match = _REQUIRED.fullmatch(clause.strip())
            if match:
                companions.update(int(value) for value in re.findall(r"\d+", match["numbers"]))
            elif re.match(r"^(Использует|Требует|Автоматически добавляет|DB bundle:)", clause.strip(), re.I):
                raise ValueError(f"Malformed dependency clause for {identifier}: {clause}")
        references.update(int(value) for value in re.findall(r"\b\d+\b", cells[4]))
        companions.discard(number)  # A bundle lists its own member too.
        harnesses.append(Harness(
            number=number,
            id=identifier,
            band=cells[2],
            companions=tuple(sorted(companions)),
            constraints=cells[4],
            primary_probe=cells[5].strip("`"),
            description=cells[3],
        ))
    if not harnesses:
        raise ValueError("Harness matrix table is missing or empty")
    unknown = references - {item.number for item in harnesses}
    if unknown:
        raise ValueError(f"Unknown harness dependency numbers: {sorted(unknown)}")
    return tuple(harnesses)


def load_matrix(repo_root: Path) -> tuple[Harness, ...]:
    return parse_matrix((Path(repo_root) / "evals/HARNESS_MATRIX.md").read_text(encoding="utf-8"))


def catalog_ids(repo_root: Path) -> tuple[str, ...]:
    """Read only ID cells in the README Catalog section, never install paths."""
    text = (Path(repo_root) / "README.md").read_text(encoding="utf-8")
    match = re.search(r"^## Catalog\s*$\n(?P<body>.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise ValueError("README Catalog section is missing")
    identifiers = tuple(re.findall(r"^\|\s*`([^`]+)`\s*\|", match["body"], re.M))
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("README Catalog IDs are missing or duplicated")
    return identifiers


def catalog_discrepancies(repo_root: Path, matrix: tuple[Harness, ...]) -> list[str]:
    """Report drift without modifying either source of truth."""
    catalog = set(catalog_ids(repo_root))
    selected = {item.id for item in matrix}
    errors = []
    if selected - catalog:
        errors.append("Matrix IDs missing from README Catalog: " + ", ".join(sorted(selected - catalog)))
    if catalog - selected:
        errors.append("README Catalog IDs missing from matrix: " + ", ".join(sorted(catalog - selected)))
    return errors
