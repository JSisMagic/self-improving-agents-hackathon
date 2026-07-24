#!/usr/bin/env python3
"""Validate the repository's specification structure using the standard library."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs"
CATALOG = SPECS / "00-governance" / "catalog.md"
ARCHIVE = SPECS / "archive"

LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
HEADING_REQUIREMENT_RE = re.compile(
    r"^### ((?:PROD|AUD|MET|ARC|DAT|FUN|WFL|INT|SEC|DEL)-(\d{3}))\b"
)
TEST_DEFINITION_RE = re.compile(r"^\| (TST-(\d{3})) \|")


def markdown_files() -> list[Path]:
    return sorted([*ROOT.glob("*.md"), *SPECS.rglob("*.md")])


def active_markdown_files(files: list[Path]) -> list[Path]:
    return [path for path in files if ARCHIVE not in path.parents]


def check_links(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for raw_target in LINK_RE.findall(line):
                target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
                if (
                    not target
                    or target.startswith(("#", "http://", "https://", "mailto:"))
                ):
                    continue
                target_path = unquote(target.split("#", 1)[0])
                resolved = (path.parent / target_path).resolve()
                if not resolved.exists():
                    errors.append(
                        f"{path.relative_to(ROOT)}:{line_number}: "
                        f"broken link {raw_target!r}"
                    )
    return errors


def check_json() -> list[str]:
    errors: list[str] = []
    for path in sorted(SPECS.rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
    return errors


def check_requirement_definitions(files: list[Path]) -> list[str]:
    definitions: dict[str, list[str]] = defaultdict(list)

    for path in files:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = HEADING_REQUIREMENT_RE.match(line)
            if path.name == "TST-001-acceptance-plan.md":
                match = match or TEST_DEFINITION_RE.match(line)
            if not match:
                continue
            requirement_id, _number = match.groups()
            definitions[requirement_id].append(
                f"{path.relative_to(ROOT)}:{line_number}"
            )

    errors: list[str] = []
    for requirement_id, locations in sorted(definitions.items()):
        if len(locations) != 1:
            errors.append(
                f"{requirement_id}: defined {len(locations)} times at "
                + ", ".join(locations)
            )

    return errors


def check_catalog(files: list[Path]) -> list[str]:
    catalog_text = CATALOG.read_text(encoding="utf-8")
    excluded = {
        SPECS / "00-governance" / "catalog.md",
        SPECS / "00-governance" / "traceability.md",
        SPECS / "00-governance" / "glossary.md",
        *SPECS.joinpath("99-templates").glob("*.md"),
    }
    errors: list[str] = []
    for path in files:
        if path.parent == ROOT or path in excluded:
            continue
        if path.name not in catalog_text:
            errors.append(f"{path.relative_to(ROOT)}: missing from catalog")
    return errors


def main() -> int:
    files = markdown_files()
    active_files = active_markdown_files(files)
    errors = [
        *check_links(files),
        *check_json(),
        *check_requirement_definitions(active_files),
        *check_catalog(active_files),
    ]
    if errors:
        print("Specification validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    requirement_count = 0
    for path in active_files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if HEADING_REQUIREMENT_RE.match(line) or (
                path.name == "TST-001-acceptance-plan.md"
                and TEST_DEFINITION_RE.match(line)
            ):
                requirement_count += 1
    print(
        f"Validated {len(active_files)} active Markdown files and "
        f"{len(files) - len(active_files)} archived Markdown files, "
        f"{len(list(SPECS.rglob('*.json')))} JSON schemas, "
        f"and {requirement_count} active requirement/test definitions."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
