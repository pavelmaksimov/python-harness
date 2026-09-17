"""Pure selection parsing, mandatory dependency closure, and probe coverage."""

from dataclasses import dataclass
import re

from .matrix import Harness


@dataclass(frozen=True)
class Selection:
    include_numbers: tuple[int, ...]
    exclude_numbers: tuple[int, ...]
    numbers: tuple[int, ...]
    harness_ids: tuple[str, ...]


_EXCEPT = re.compile(r"\b(?:кроме|исключи|except|exclude)\b", re.IGNORECASE)
_TOKEN = re.compile(
    r"(?P<space>[\s,;]+)|"
    r"(?P<join>\b(?:и|and|включи|include|исключи|exclude|кроме|except)\b)|"
    r"(?P<standard>\b(?:все\s+стандартное|all\s+standard|standard\s+all)\b)|"
    r"(?P<all>\b(?:все|all)\b)|"
    r"(?P<range>[0-9]+\s*[-–—]\s*[0-9]+)|"
    r"(?P<number>[0-9]+)"
)


def _numbers(value: str | tuple[int, ...], matrix: tuple[Harness, ...]) -> set[int]:
    known = {item.number for item in matrix}
    if isinstance(value, tuple):
        if any(type(number) is not int for number in value):
            raise ValueError("Harness numbers must be integers")
        numbers = set(value)
    elif isinstance(value, str):
        text = value.casefold().replace("ё", "е")
        numbers = set()
        offset = 0
        while offset < len(text):
            match = _TOKEN.match(text, offset)
            if not match:
                raise ValueError(f"Invalid selection token: {text[offset:]!r}")
            offset = match.end()
            kind = match.lastgroup
            if kind == "standard":
                numbers.update(item.number for item in matrix
                               if "optional" not in item.band.split() and not item.future_probe)
            elif kind == "all":
                numbers.update(known)
            elif kind == "range":
                first, last = map(int, re.split(r"\s*[-–—]\s*", match.group()))
                if first > last:
                    raise ValueError(f"Descending harness range: {match.group()}")
                if first not in known or last not in known:
                    raise ValueError(f"Unknown harness range: {match.group()}")
                numbers.update(range(first, last + 1))
            elif kind == "number":
                numbers.add(int(match.group()))
    else:
        raise ValueError("Selection must be text or a tuple of harness numbers")
    unknown = numbers - known
    if unknown:
        raise ValueError(f"Unknown harness numbers: {sorted(unknown)}")
    return numbers


def resolve_selection(
    include: str | tuple[int, ...],
    exclude: str | tuple[int, ...],
    matrix: tuple[Harness, ...],
) -> Selection:
    """Expand include roots, close mandatory edges, then apply exclusions.

    Numbers always use matrix order, independent of token order or repetition.
    Excluding a dependency is a conflict whenever its dependent remains selected.
    Optional entries participate in explicit ``all`` but not ``all standard``.
    """
    inline_excluded = set()
    if isinstance(include, str):
        parts = _EXCEPT.split(include)
        include = parts[0]
        for part in parts[1:]:
            if not part.strip():
                raise ValueError("An exclusion keyword must be followed by harness numbers")
            inline_excluded.update(_numbers(part, matrix))
    included = _numbers(include, matrix)
    if isinstance(exclude, str):
        parts = _EXCEPT.split(exclude)
        excluded = set()
        for index, part in enumerate(parts):
            if index and not part.strip():
                raise ValueError("An exclusion keyword must be followed by harness numbers")
            excluded.update(_numbers(part, matrix))
    else:
        excluded = _numbers(exclude, matrix)
    excluded.update(inline_excluded)
    by_number = {item.number: item for item in matrix}
    expanded = set(included)
    pending = list(included)
    while pending:
        for dependency in by_number[pending.pop()].companions:
            if dependency not in expanded:
                expanded.add(dependency)
                pending.append(dependency)
    remaining = expanded - excluded
    for number in sorted(remaining):
        for dependency in by_number[number].companions:
            if dependency in excluded:
                raise ValueError(
                    f"Harness {number} ({by_number[number].id}) requires companion "
                    f"{dependency} ({by_number[dependency].id}), which was explicitly excluded"
                )
    if not remaining:
        raise ValueError("No harnesses selected")
    numbers = tuple(sorted(remaining))
    return Selection(
        include_numbers=tuple(sorted(included)),
        exclude_numbers=tuple(sorted(excluded)),
        numbers=numbers,
        harness_ids=tuple(by_number[number].id for number in numbers),
    )


def ensure_coverage(
    selection: Selection, tasks: list[dict], matrix: tuple[Harness, ...]
) -> None:
    """Require a real task intersection, without inventing future probe coverage.

    General-workflow entries are always covered. Requesting a harness whose probe
    does not exist yet is refused outright — closing over its companions must not
    make an unprobed experiment look supported. Coverage declarations belong to
    tasks, not to a second number registry here.
    """
    by_number = {item.number: item for item in matrix}
    roots = set(selection.include_numbers) - set(selection.exclude_numbers)
    active = {number for number in selection.numbers if not by_number[number].general_workflow}
    if not active:
        return
    requested = {number for number in roots if not by_number[number].general_workflow} or active
    unprobed = {number for number in requested if by_number[number].future_probe}
    if unprobed:
        identifiers = ", ".join(by_number[number].id for number in sorted(unprobed))
        raise ValueError(
            f"No probe covers {identifiers} yet; create a separate bounded task "
            "before running the experiment"
        )
    eligible = {
        number for number in selection.numbers
        if not by_number[number].general_workflow and not by_number[number].future_probe
    }
    covered = set()
    for task in tasks:
        values = task.get("covered_numbers", [])
        if not isinstance(values, (list, tuple)) or any(type(number) is not int for number in values):
            raise ValueError("Task covered_numbers must be a list of integers")
        unknown = set(values) - by_number.keys()
        if unknown:
            raise ValueError(f"Task coverage contains unknown harness numbers: {sorted(unknown)}")
        covered.update(values)
    if any(not by_number[number].future_probe for number in requested) and eligible & covered:
        return
    identifiers = ", ".join(by_number[number].id for number in sorted(requested))
    raise ValueError(
        f"Probe does not cover {identifiers}; create a separate bounded task "
        "before running the experiment"
    )


def format_selection(selection: Selection) -> str:
    included = ",".join(map(str, selection.include_numbers)) or "none"
    excluded = ",".join(map(str, selection.exclude_numbers)) or "none"
    return f"include={included}; exclude={excluded}; harness_ids={','.join(selection.harness_ids)}"
