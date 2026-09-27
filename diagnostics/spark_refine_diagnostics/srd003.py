"""SRD003: proof depends on the prover portfolio.

Observed in this repository (fixed pool, Tasks 003/004): the racing
portfolio proves everything; CVC5 alone and Z3 alone leave checks unproved;
Alt-Ergo alone proves all of them.

Rule, over >= 2 named single-prover runs of the same sources:

    check K is CONFIDENTLY matched across all runs
    and K is PROVED in >= 1 run and UNPROVED in >= 1 other run
    => SRD003 for K   (match_quality in the diagnostic)

Matching policy (deterministic; the analyzer prefers "unmatched" over
"incorrectly correlated"; SARIF result order is irrelevant):

  level 1  exact          (rule, file, line, column, entity) occurs exactly
                          once in every compared run
  level 2  fingerprint    NOT AVAILABLE: FSF GNATprove 16.1.0 SARIF results
                          carry no fingerprints / partialFingerprints /
                          guid / correlationGuid (checked on all 58 raw
                          logs of Tasks 001-005); nothing is synthesised
                          from message text
  level 3  unique_entity  identities left over by level 1 whose
                          (rule, file, entity) occurs exactly once in every
                          run, counting ALL checks of the run. GNATprove
                          reports a proved postcondition at the aspect and
                          an unproved one at the failing conjunct, so line
                          and column legitimately differ; if the entity has
                          a single check of that rule in that file in every
                          run, there is nothing to confuse it with.

Everything else is NOT paired and never produces SRD003:

  duplicate_identity    one exact identity occurs several times in a run
                        (e.g. a container aggregate check reported once per
                        instantiation)
  ambiguous_candidates  leftovers exist in every run, but (rule, file,
                        entity) is not unique in some run
  unmatched             some run has no candidate at all

These are reported in the analysis metadata (MatchResult.to_dict), with
candidates ordered by source position ("candidate ordinal i of n") as
context only; source order never decides a pairing.

An optional portfolio (reference) run is shown for context only, resolved
with the same identity levels ("absent" / "ambiguous" otherwise).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from .model import (Check, Confidence, Diagnostic, Location, ProofRun,
                    Severity, Status)
from .rules import make, related

CheckKey = tuple  # (rule, file, line, column, entity)
EntityKey = tuple  # (rule, file, entity)

EXACT = "exact"
UNIQUE_ENTITY = "unique_entity"
CONFIDENT_QUALITIES = (EXACT, UNIQUE_ENTITY)
FINGERPRINT_SUPPORT = ("not available: GNATprove 16.1.0 SARIF has no "
                       "fingerprints, partialFingerprints or guid")


def exact_key(c: Check) -> CheckKey:
    return (c.rule, c.location.file, c.location.line or 0,
            c.location.column or 0, c.entity)


def entity_key(c: Check) -> EntityKey:
    return (c.rule, c.location.file, c.entity)


@dataclass
class MatchedCheck:
    key: CheckKey          # exact identity; for unique_entity, that of the
                           # unproved occurrence (independent of run order)
    quality: str           # EXACT | UNIQUE_ENTITY
    per_run: dict[str, Check]


@dataclass
class Unresolved:
    reason: str            # duplicate_identity | ambiguous_candidates |
                           # unmatched
    key: EntityKey
    per_run: dict[str, list[Check]]

    def outcomes_differ(self) -> bool:
        multisets = {tuple(sorted(c.status.value for c in cs))
                     for cs in self.per_run.values() if cs}
        return len(multisets) > 1

    def to_dict(self, names: list[str]) -> dict:
        rule, file, entity = self.key
        runs = {}
        for n in names:
            cs = sorted(self.per_run.get(n, []),
                        key=lambda c: (c.location.line or 0,
                                       c.location.column or 0,
                                       c.status.value))
            runs[n] = [{"candidate": f"{i} of {len(cs)}",
                        "line": c.location.line,
                        "column": c.location.column,
                        "status": c.status.value}
                       for i, c in enumerate(cs, 1)]
        return {"reason": self.reason, "rule": rule, "file": file,
                "entity": entity, "outcomes_differ": self.outcomes_differ(),
                "candidates": runs}


@dataclass
class MatchResult:
    names: list[str]
    matched: list[MatchedCheck]
    unresolved: list[Unresolved]

    def counts(self) -> dict:
        c = Counter(m.quality for m in self.matched)
        u = Counter(x.reason for x in self.unresolved)
        return {"exact": c[EXACT], "fingerprint": 0,
                "unique_entity": c[UNIQUE_ENTITY],
                "duplicate_identity": u["duplicate_identity"],
                "ambiguous_candidates": u["ambiguous_candidates"],
                "unmatched": u["unmatched"]}

    def to_dict(self) -> dict:
        return {"runs": list(self.names),
                "policy": ["exact", "fingerprint", "unique_entity"],
                "fingerprint_support": FINGERPRINT_SUPPORT,
                "counts": self.counts(),
                "unresolved": [u.to_dict(self.names)
                               for u in self.unresolved]}


def match_checks(runs: list[ProofRun]) -> MatchResult:
    names = [r.name for r in runs]
    by_key: dict[str, dict[CheckKey, list[Check]]] = {
        r.name: defaultdict(list) for r in runs}
    ent_total: dict[str, Counter] = {}
    for r in runs:
        for c in r.checks:
            by_key[r.name][exact_key(c)].append(c)
        ent_total[r.name] = Counter(entity_key(c) for c in r.checks)
    matched: list[MatchedCheck] = []
    unresolved: list[Unresolved] = []
    leftovers: dict[EntityKey, dict[str, list[Check]]] = defaultdict(
        lambda: defaultdict(list))
    for key in sorted(set().union(*(set(k) for k in by_key.values()))):
        present = {n: by_key[n].get(key, []) for n in names}
        if any(len(cs) > 1 for cs in present.values()):
            rule, file, _l, _c, entity = key
            unresolved.append(Unresolved("duplicate_identity",
                                         (rule, file, entity), present))
        elif all(len(cs) == 1 for cs in present.values()):
            matched.append(MatchedCheck(key, EXACT,
                                        {n: present[n][0] for n in names}))
        else:
            for n, cs in present.items():
                if cs:
                    leftovers[entity_key(cs[0])][n].append(cs[0])
    for ek in sorted(leftovers):
        per = leftovers[ek]
        if all(len(per.get(n, [])) == 1 and ent_total[n][ek] == 1
               for n in names):
            # canonical key independent of run order: the identity of an
            # unproved occurrence (the failing conjunct) if any, else the
            # smallest location
            occ = [per[n][0] for n in names]
            key = min((exact_key(c) for c in occ if c.unproved),
                      default=min(exact_key(c) for c in occ))
            matched.append(MatchedCheck(key, UNIQUE_ENTITY,
                                        {n: per[n][0] for n in names}))
        else:
            reason = ("ambiguous_candidates" if all(per.get(n)
                                                    for n in names)
                      else "unmatched")
            unresolved.append(Unresolved(reason, ek, dict(per)))
    matched.sort(key=lambda m: (m.key, m.quality))
    unresolved.sort(key=lambda u: (u.key, u.reason))
    return MatchResult(names, matched, unresolved)


def _reference_status(ref: ProofRun, m: MatchedCheck) -> str:
    exact = [c for c in ref.checks if exact_key(c) == m.key]
    if len(exact) == 1:
        return exact[0].status.value
    ek = (m.key[0], m.key[1], m.key[4])
    same = [c for c in ref.checks if entity_key(c) == ek]
    if not exact and len(same) == 1:
        return same[0].status.value
    return "absent" if not exact and not same else "ambiguous"


def evaluate(runs: list[ProofRun], reference: ProofRun | None = None
             ) -> tuple[list[Diagnostic], MatchResult | None]:
    if len(runs) < 2:
        return [], None
    names = [r.name for r in runs]
    all_names = names + ([reference.name] if reference else [])
    if len(set(all_names)) != len(all_names):
        raise ValueError(f"run names must be unique: {all_names}")
    result = match_checks(runs)
    out = []
    for m in result.matched:
        statuses = {n: m.per_run[n].status.value for n in names}
        proved_in = [n for n in names if statuses[n] == Status.PROVED.value]
        unproved_in = [n for n in names
                       if statuses[n] == Status.UNPROVED.value]
        if proved_in and unproved_in:
            out.append(_diagnostic(m, names, statuses, proved_in,
                                   unproved_in, reference))
    return out, result


def _diagnostic(m, names, statuses, proved_in, unproved_in, reference):
    rule, file, line, col, entity = m.key
    results = [(n, statuses[n]) for n in names]
    rel = [related(m.per_run[n].status.value, m.per_run[n], run=n)
           for n in names]
    if reference:
        results.append((f"{reference.name} (reference)",
                        _reference_status(reference, m)))
    evidence = [f"{n}: {s}" for n, s in results]
    if m.quality == EXACT:
        evidence.append("cross-run identity: exact (rule, file, line, "
                        "column, entity), unique in every run")
    else:
        locs = ", ".join(f"{n} {m.per_run[n].location}" for n in names)
        evidence.append("cross-run identity: unique_entity (rule, file, "
                        "entity) has exactly one check in every run; "
                        f"locations differ: {locs}")
    disputed = [n for n in names if m.per_run[n].disputed]
    if disputed:
        evidence.append("SARIF/.spark status disagreement in "
                        f"{', '.join(disputed)}: confidence lowered")
    return make(
        "SRD003",
        severity=Severity.NOTE,
        confidence=Confidence.MEDIUM if disputed else Confidence.HIGH,
        entity=entity,
        primary_location=Location(file, line or None, col or None),
        explanation=(
            f"{rule} is proved by {', '.join(proved_in)} but not by "
            f"{', '.join(unproved_in)}. The proof stays green only while "
            "the portfolio contains a prover that discharges it. This "
            "is robustness/maintenance information, not unsoundness."),
        recommendation=(
            "Keep the prover portfolio (and prover versions) pinned in "
            "CI. If long-term portability across provers matters, "
            "consider strengthening the proof, e.g. with an "
            "intermediate assertion or a reusable lemma."),
        evidence=tuple(evidence),
        related=tuple(rel),
        data=(("rule", rule), ("results", tuple(results))),
        match_quality=m.quality)


def check(runs: list[ProofRun], reference: ProofRun | None = None
          ) -> list[Diagnostic]:
    return evaluate(runs, reference)[0]
