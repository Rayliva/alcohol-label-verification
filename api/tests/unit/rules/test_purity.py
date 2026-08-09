"""The rule engine is pure — docs/specs/rule-engine.md §1, acceptance criterion 15.

`rules/` takes data and returns verdicts. The moment it imports the OCR or
extraction layer it stops being unit-testable without a network, and the
fastest-feedback package in the build becomes the slowest. This test is the
guard on that boundary, checked on every commit rather than in review.
"""

from __future__ import annotations

import ast
from pathlib import Path

RULES = Path(__file__).resolve().parents[3] / "app" / "rules"

FORBIDDEN = ("app.ocr", "app.extraction", "app.main", "app.bench")


def _imported_modules(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_rules_does_not_import_the_io_layers() -> None:
    offenders: dict[str, set[str]] = {}
    for source in RULES.rglob("*.py"):
        bad = {m for m in _imported_modules(source) if m.startswith(FORBIDDEN)}
        if bad:
            offenders[str(source.relative_to(RULES))] = bad
    assert not offenders, f"rules/ must stay pure, but these import I/O layers: {offenders}"


def test_rules_does_not_import_a_network_or_filesystem_client() -> None:
    heavy = ("anthropic", "google", "httpx", "requests", "cv2", "PIL", "fastapi")
    offenders: dict[str, set[str]] = {}
    for source in RULES.rglob("*.py"):
        bad = {m for m in _imported_modules(source) if m.startswith(heavy)}
        if bad:
            offenders[str(source.relative_to(RULES))] = bad
    assert not offenders, f"rules/ must stay pure, but these reach outside: {offenders}"
