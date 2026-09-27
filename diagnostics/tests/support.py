"""Shared helpers for the diagnostics tests (stdlib unittest only)."""

from __future__ import annotations

import sys
import tomllib
from functools import lru_cache
from pathlib import Path

TESTS = Path(__file__).resolve().parent
DIAGNOSTICS = TESTS.parent
REPO = DIAGNOSTICS.parent
FIXTURES = TESTS / "fixtures"

if str(DIAGNOSTICS) not in sys.path:
    sys.path.insert(0, str(DIAGNOSTICS))

from spark_refine_diagnostics import analyze_path, load_run  # noqa: E402


def manifest() -> dict:
    return tomllib.loads((FIXTURES / "manifest.toml").read_text("utf-8"))


def fixture(name: str) -> Path:
    path = FIXTURES / name
    if not (path / "gnatprove.sarif").is_file():
        raise AssertionError(f"fixture {name} is missing gnatprove.sarif")
    return path


@lru_cache(maxsize=None)
def expectations() -> dict:
    return tomllib.loads((TESTS / "expectations.toml").read_text("utf-8"))


def expected(name: str) -> dict:
    return expectations()[name]


@lru_cache(maxsize=None)
def analyzed(name: str):
    return analyze_path(fixture(name), name=name)


@lru_cache(maxsize=None)
def run_of(name: str):
    return load_run(fixture(name), name=name)


def codes(diags) -> list[str]:
    return sorted(d.code for d in diags)


def by_code(diags, code: str) -> list:
    return [d for d in diags if d.code == code]


def unproved_pairs(run) -> set[tuple[str, str]]:
    return {(c.rule, c.entity) for c in run.unproved}
