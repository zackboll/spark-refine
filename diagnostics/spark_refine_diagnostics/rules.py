"""Stable diagnostic rule catalogue and shared helpers.

IDs never depend on line numbers or message text. Adding a rule appends a
new code; existing codes keep their meaning.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Check, Confidence, Diagnostic, RelatedCheck, Severity


@dataclass(frozen=True)
class RuleInfo:
    code: str
    title: str
    # Default confidence. When `confidence_policy` is set, the confidence of
    # each emitted diagnostic is decided per diagnostic by that policy.
    confidence: Confidence
    scope: str
    summary: str
    confidence_policy: str = ""

    @property
    def confidence_label(self) -> str:
        return "dynamic" if self.confidence_policy else self.confidence.value


INVARIANT_RULE = "VC_INVARIANT_CHECK"
POSTCONDITION_RULE = "VC_POSTCONDITION"
PRECONDITION_RULE = "VC_PRECONDITION"
ASSERT_RULE = "VC_ASSERT"
CLIENT_OBLIGATION_RULES = frozenset({PRECONDITION_RULE, ASSERT_RULE})

# SRD002 confidence per failing client rule. A client-only precondition gap
# often points at an abstraction that exposes too little; a client-only
# assertion failure is just as often an assertion that is too strong or
# false. A diagnostic aggregating several rules takes the LOWEST confidence.
SRD002_CONFIDENCE = {PRECONDITION_RULE: Confidence.MEDIUM,
                     ASSERT_RULE: Confidence.LOW}
_CONFIDENCE_ORDER = (Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH)


def lowest_confidence(values) -> Confidence:
    return min(values, key=_CONFIDENCE_ORDER.index)


RULES: dict[str, RuleInfo] = {r.code: r for r in (
    RuleInfo(
        "SRD001", "failed invariant may mask downstream postconditions",
        Confidence.HIGH, "single run",
        "An entity has an unproved VC_INVARIANT_CHECK and at least one "
        "proved VC_POSTCONDITION. Those postconditions may be conditional "
        "on the invariant that GNATprove assumes after checking it. High "
        "confidence refers to the structural masking risk only: it never "
        "claims that a postcondition depends on the invariant, that it is "
        "false, or that GNATprove proved the wrong theorem."),
    RuleInfo(
        "SRD002",
        "Client-only proof gap; public abstraction may be insufficient",
        Confidence.MEDIUM, "single run",
        "A client unit has unproved VC_PRECONDITION/VC_ASSERT checks while "
        "every analysed unit in its .ali dependency closure is fully "
        "proved. Possible causes: the public contracts expose too little "
        "abstraction information; the client property is too strong or "
        "false; an intermediate client assertion is missing; the client "
        "needs a stronger precondition. Not evaluated when dependency "
        "information is unavailable.",
        confidence_policy=(
            "medium for VC_PRECONDITION, low for VC_ASSERT; lowest applies "
            "when one diagnostic has both")),
    RuleInfo(
        "SRD003", "proof depends on prover portfolio",
        Confidence.HIGH, "multiple runs",
        "A check is proved in at least one single-prover run and unproved "
        "in at least one other. Emitted only for confidently matched "
        "checks (match_quality exact or unique_entity); ambiguous "
        "identities are reported as analysis metadata instead. Robustness "
        "information, not unsoundness."),
)}


def related(role: str, c: Check, run: str | None = None) -> RelatedCheck:
    return RelatedCheck(role=role, rule=c.rule, status=c.status.value,
                        entity=c.entity, location=c.location,
                        message=c.message, run=run)


def loc_key(c: Check) -> tuple:
    return (c.location.file, c.location.line or 0, c.location.column or 0,
            c.rule)


def make(code: str, **kw) -> Diagnostic:
    info = RULES[code]
    kw.setdefault("confidence", info.confidence)
    kw.setdefault("severity", Severity.WARNING)
    return Diagnostic(code=code, title=info.title, **kw)
