"""SRD002: client-only proof gap; public abstraction may be insufficient.

Observed in this repository (ring buffer Task 001 ablations
no_public_model_bound / no_is_empty_post / no_is_full_post; fixed pool
Task 003 ablation spec_no_count_posts): the implementation proves, but the
client proof cannot establish an operation precondition or an assertion.

What SRD002 means (and does not mean). The rule detects a CLIENT-ONLY PROOF
GAP: every implementation unit the client depends on is proved, and the
client still cannot discharge a precondition or an assertion. That alone
does not show that the public abstraction is insufficient. Possible causes:

  - the public contracts expose insufficient abstraction information;
  - the client property is simply too strong or false;
  - an intermediate client assertion is missing;
  - the client needs a stronger precondition.

The MVP has no semantic evidence to tell these apart, so SRD002 never says
that a public contract IS insufficient (fixture pool_false_client_assert:
a false client assertion over a fully proved pool also triggers SRD002, at
low confidence, and that is correct under this definition).

Rule, per client unit C:

    D = transitive closure of C's dependencies (GNAT .ali W/Z records),
        restricted to the analysed units, minus C; only units with >= 1
        check carry evidence (SPARK_Mode => Off drivers are ignored)
    D is not empty
    and C has >= 1 UNPROVED VC_PRECONDITION / VC_ASSERT
    and every unit in D has 0 unproved, 0 justified checks, completed
        analysis (stop_reason NONE) and no SARIF/.spark disagreement
    => one SRD002 per client entity with such failures

If any unit in D has an unproved check, SRD002 is NOT emitted for C: the
client failure may just be a consequence of the implementation problem.

Confidence (rules.SRD002_CONFIDENCE), per diagnostic:

    only VC_PRECONDITION failures   medium
    any VC_ASSERT failure           low   (lowest applicable confidence)

Dependency information: .ali (ali.load_ali_deps) or --client-unit. When it
is unavailable (missing / empty / truncated / malformed .ali), SRD002 is
not evaluated at all and the analysis says so; dependencies are never
guessed from file names.

Other unproved checks of the client (e.g. its own postconditions) do not
block the rule; they are listed as context. No Ada semantics are used: the
failing call, the callee and any insufficient contract are NOT identified.
Message text is shown, never required. (Task 009: the optional --semantic
enrichment, semantic.py, may afterwards ADD source context to an emitted
SRD002; it never influences this rule.)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .ali import AliDeps
from .model import Check, Diagnostic, ProofRun
from .rules import (CLIENT_OBLIGATION_RULES, SRD002_CONFIDENCE, loc_key,
                    lowest_confidence, make, related)

POSSIBLE_CAUSES = (
    "the public contracts may expose insufficient abstraction information",
    "the client property may simply be too strong or false",
    "an intermediate client assertion may be missing",
    "the client may need a stronger precondition",
)

_EXPLANATION = {
    "VC_PRECONDITION": (
        "The implementation units are proved, but this client cannot "
        "establish a called operation's precondition. This often indicates "
        "that the public abstraction does not expose enough information, "
        "but the client's own precondition or reasoning may also be "
        "insufficient."),
    "VC_ASSERT": (
        "The implementation units are proved, but this client assertion "
        "cannot be established. The assertion may be too strong or false, "
        "or the public abstraction may not expose enough information to "
        "prove it."),
}


@dataclass
class UnitGraph:
    """Analysed units -> analysed units in their dependency closure.
    `source`: "ali" (GNAT .ali W/Z records), "explicit" (--client-unit) or
    "none" (SRD002 cannot be evaluated; `reason` says why)."""

    deps: dict[str, set[str]] = field(default_factory=dict)
    source: str = "none"
    reason: str = ""


def _closure(direct: dict[str, set[str]], unit: str) -> set[str]:
    seen: set[str] = set()
    todo = [unit]
    while todo:
        for d in direct.get(todo.pop(), ()):
            if d not in seen:
                seen.add(d)
                todo.append(d)
    seen.discard(unit)
    return seen


def build_unit_graph(run: ProofRun, ali: AliDeps | None,
                     client_units: list[str] | None = None) -> UnitGraph:
    units = set(run.dependency_unit_names())
    if client_units:
        clients = {c.lower() for c in client_units}
        deps = {u: (units - clients if u in clients else set())
                for u in units | clients}
        return UnitGraph(deps=deps, source="explicit")
    if ali is None:
        return UnitGraph(reason="no .ali dependency information supplied")
    if not ali.ok:
        return UnitGraph(reason="; ".join(ali.problems)
                         or "ALI dependency information unavailable")
    missing = sorted(units - set(ali.deps))
    if missing:
        return UnitGraph(reason="no .ali file for analysed unit(s) "
                                + ", ".join(missing))
    direct = {u: ali.deps[u] & units for u in units}
    return UnitGraph(deps={u: _closure(direct, u) for u in units},
                     source="ali")


def evaluate(run: ProofRun, graph: UnitGraph
             ) -> tuple[list[Diagnostic], list[str]]:
    """Returns (diagnostics, notes). Notes record clients that had a
    qualifying failure but were deliberately not reported."""
    if graph.source == "none":
        return [], []
    by_unit: dict[str, list[Check]] = defaultdict(list)
    for c in run.checks:
        if c.unit:
            by_unit[c.unit].append(c)
    complete = {u.name: u.complete for u in run.units}
    out: list[Diagnostic] = []
    notes: list[str] = []
    for client in sorted(graph.deps):
        # Units without any check (e.g. SPARK_Mode => Off test drivers)
        # carry no evidence either way and are ignored; at least one
        # dependency with checks is required, so "green" is never vacuous.
        impl = sorted(u for u in graph.deps[client] if by_unit.get(u))
        if not impl:
            continue
        failures = sorted((c for c in by_unit.get(client, [])
                           if c.unproved
                           and c.rule in CLIENT_OBLIGATION_RULES),
                          key=loc_key)
        if not failures:
            continue
        impl_failures = sum(c.unproved or c.justified
                            for u in impl for c in by_unit[u])
        if impl_failures or not all(complete.get(u, True) for u in impl):
            continue
        disputed = sorted(u for u in [client, *impl]
                          if u in run.disputed_units)
        if disputed:
            notes.append(f"SRD002 not emitted for client {client}: "
                         "SARIF/.spark disagree on unit(s) "
                         f"{', '.join(disputed)}")
            continue
        impl_total = sum(len(by_unit[u]) for u in impl)
        per_entity: dict[str, list[Check]] = defaultdict(list)
        for c in failures:
            per_entity[c.entity].append(c)
        for entity in sorted(per_entity):
            out.append(_diagnostic(client, entity, per_entity[entity],
                                   by_unit[client], impl, impl_total,
                                   graph.source))
    return out, notes


def _diagnostic(client, entity, fails, client_checks, impl, impl_total,
                source) -> Diagnostic:
    others = sorted((c for c in client_checks
                     if c.unproved and c.entity == entity
                     and c not in fails), key=loc_key)
    rules = sorted({c.rule for c in fails})
    confidence = lowest_confidence(SRD002_CONFIDENCE[r] for r in rules)
    evidence = [
        f"client unit {client}: {len(fails)} unproved "
        f"{'/'.join(rules)} in {entity}",
        f"implementation unit(s) {', '.join(impl)}: {impl_total} checks, "
        "0 unproved, 0 justified",
        f"unit dependencies from: {source}",
        f"confidence {confidence.value}: "
        + ", ".join(f"{r} -> {SRD002_CONFIDENCE[r].value}" for r in rules)
        + " (lowest applies)",
    ]
    if others:
        evidence.append(f"{len(others)} other unproved check(s) in "
                        f"{entity} (context only)")
    explanation = " ".join(_EXPLANATION[r] for r in rules) + (
        " This is a client-only proof gap; possible causes: "
        + "; ".join(POSSIBLE_CAUSES) + ". The analyzer does not identify "
        "the called operation or any specific contract.")
    return make(
        "SRD002",
        confidence=confidence,
        entity=entity,
        primary_location=fails[0].location,
        explanation=explanation,
        recommendation=(
            "First check that the client property is actually true and "
            "that the client's own precondition is strong enough; an "
            "intermediate assertion may help. If so, inspect the public "
            "contracts of the operations called at the listed locations and "
            "of the related query/model functions. Do not expose the "
            "private representation merely to fix the client."),
        evidence=tuple(evidence),
        related=tuple([related("client failure", c) for c in fails]
                      + [related("client context", c) for c in others]),
        data=(("client_unit", client),
              ("client_rules", tuple(rules)),
              ("implementation_units", tuple(impl)),
              ("implementation_checks", impl_total),
              ("implementation_failures", 0),
              ("dependency_source", source)))


def check(run: ProofRun, graph: UnitGraph) -> list[Diagnostic]:
    return evaluate(run, graph)[0]
