"""Normalized, tool-independent model of a GNATprove run and of diagnostics.

Everything here is plain data. Parsing lives in sarif.py / spark_results.py /
loader.py, rules live in analyzer.py, presentation lives in render.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    """Outcome of one GNATprove check, decided structurally.

    PROVED     SARIF kind == "pass"
    JUSTIFIED  not passed, but carries an in-source SARIF suppression
               (pragma Annotate (GNATprove, False_Positive/Intentional, ...))
    UNPROVED   any other non-passing check result
    """

    PROVED = "proved"
    JUSTIFIED = "justified"
    UNPROVED = "unproved"


class Severity(str, Enum):
    WARNING = "warning"
    NOTE = "note"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, order=True)
class Location:
    file: str
    line: int | None = None
    column: int | None = None

    def __str__(self) -> str:
        out = self.file
        if self.line is not None:
            out += f":{self.line}"
            if self.column is not None:
                out += f":{self.column}"
        return out


@dataclass(frozen=True)
class ProverStat:
    """Per-prover statistics from a .spark proof entry (measurement only)."""

    prover: str
    count: int
    max_steps: int
    max_time: float


@dataclass(frozen=True)
class Check:
    """One verification condition / flow check reported by GNATprove."""

    rule: str
    status: Status
    location: Location
    entity: str
    message: str
    # Raw structural fields the status was derived from.
    sarif_kind: str = ""
    sarif_level: str = ""
    suppressions: tuple[str, ...] = ()
    # Enrichment from the .spark files (None / () when unavailable).
    unit: str | None = None
    spark_severity: str | None = None
    prover_stats: tuple[ProverStat, ...] = ()
    # True when SARIF and the unit's .spark file disagree on whether this
    # check is proved. SARIF stays authoritative for `status`, but no
    # diagnostic may rely on a disputed status with full confidence.
    disputed: bool = False

    @property
    def justified(self) -> bool:
        return self.status is Status.JUSTIFIED

    @property
    def proved(self) -> bool:
        return self.status is Status.PROVED

    @property
    def unproved(self) -> bool:
        return self.status is Status.UNPROVED


@dataclass(frozen=True)
class ToolWarning:
    """A non-check SARIF result reported at warning/note level (for example
    'function Is_Valid is assumed to return True'). `allowed` marks entries
    of the documented foundation allow-list shared with the benchmark gates."""

    rule: str
    location: Location
    entity: str
    message: str
    allowed: bool


@dataclass(frozen=True)
class UnitResult:
    """Per-unit facts from a <unit>.spark file."""

    name: str
    stop_reason: str
    pragma_assume: int
    proof_entries: int
    flow_entries: int
    unproved_entries: int  # severity in low/medium/high/error

    @property
    def complete(self) -> bool:
        return self.stop_reason == "STOP_REASON_NONE"


@dataclass
class ProofRun:
    name: str
    source: str
    tool_version: str
    command_line: str
    exit_code: int | None
    checks: list[Check] = field(default_factory=list)
    warnings: list[ToolWarning] = field(default_factory=list)
    units: list[UnitResult] = field(default_factory=list)
    # Structural disagreements between SARIF and .spark (never silently
    # ignored; rendered with the report).
    consistency_issues: list[str] = field(default_factory=list)
    # How each check's unit was attributed: "spark" (owning .spark file) or
    # "entity" (first component of the SARIF logical entity name).
    unit_attribution: str = "spark"
    # Units with any SARIF/.spark disagreement (their proof state is not
    # established unambiguously).
    disputed_units: set[str] = field(default_factory=set)

    @property
    def proved(self) -> list[Check]:
        return [c for c in self.checks if c.status is Status.PROVED]

    @property
    def unproved(self) -> list[Check]:
        return [c for c in self.checks if c.status is Status.UNPROVED]

    @property
    def justified(self) -> list[Check]:
        return [c for c in self.checks if c.status is Status.JUSTIFIED]

    @property
    def complete(self) -> bool:
        """True when every analysed unit finished (STOP_REASON_NONE) and
        SARIF and .spark agree. Unknown (no .spark) counts as complete for
        SARIF-only input; unit_attribution records the weaker evidence."""
        return (all(u.complete for u in self.units)
                and not self.consistency_issues)

    def unit_names(self) -> list[str]:
        names = {u.name for u in self.units}
        names.update(c.unit for c in self.checks if c.unit)
        return sorted(names)

    def summary(self) -> dict:
        return {
            "checks": len(self.checks),
            "proved": len(self.proved),
            "unproved": len(self.unproved),
            "justified": len(self.justified),
            "warnings": len(self.warnings),
            "allowed_foundation_warnings": sum(w.allowed
                                               for w in self.warnings),
            "pragma_assume": sum(u.pragma_assume for u in self.units),
        }


@dataclass(frozen=True)
class RelatedCheck:
    """A check cited by a diagnostic, with the role it plays in it."""

    role: str
    rule: str
    status: str
    entity: str
    location: Location
    message: str
    run: str | None = None


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: Severity
    confidence: Confidence
    title: str
    entity: str
    primary_location: Location | None
    explanation: str
    recommendation: str
    evidence: tuple[str, ...] = ()
    related: tuple[RelatedCheck, ...] = ()
    # Rule-specific structured data (for example SRD003 per-run results).
    data: tuple[tuple[str, object], ...] = ()
    # SRD003 only: how the cross-run check identity was established
    # ("exact" or "unique_entity"; see srd003.py). Never "ambiguous".
    match_quality: str | None = None

    def sort_key(self) -> tuple:
        loc = self.primary_location or Location("")
        return (self.code, self.entity, loc.file, loc.line or 0,
                loc.column or 0)


@dataclass
class Report:
    """Result of one analysis: runs, diagnostics, human-readable notes and
    structured analysis metadata (rule evaluation status, SRD003 matching
    statistics, ...). Rendered by render.to_text / render.to_json."""

    runs: list[ProofRun]
    diagnostics: list[Diagnostic]
    notes: list[str]
    analysis: dict = field(default_factory=dict)
