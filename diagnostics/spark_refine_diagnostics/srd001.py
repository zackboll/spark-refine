"""SRD001: failed type invariant may mask downstream postconditions.

Observed in this repository (ring buffer B3/B4, fixed pool P1/P5 and
library-backed L1/L5): a VC_INVARIANT_CHECK fails, GNATprove then assumes
the invariant, and a postcondition that is really false is reported proved
under the contradictory assumption.

Structural rule, per logical entity E:

    some VC_INVARIANT_CHECK of E is UNPROVED
    and some VC_POSTCONDITION of E is PROVED
    => SRD001 for E

Causality limits. Without a proof-dependency graph (GNATprove's
SARIF/.spark output does not expose which hypotheses a proof used), the
evidence is exactly:

    same entity + failed invariant + proved postcondition
    + known GNATprove invariant semantics (checked, then assumed)
    = masking RISK

SRD001 never claims that the postcondition definitely depends on the failed
invariant, that the postcondition is false, or that GNATprove proved the
wrong theorem. Justified invariant checks do not trigger the rule.

If SARIF and .spark disagree on any cited check's status (Check.disputed),
the diagnostic is still reported but its confidence drops to medium and the
evidence says why: the structural pattern itself is then not established.
"""

from __future__ import annotations

from collections import defaultdict

from .model import Check, Confidence, Diagnostic, ProofRun
from .rules import INVARIANT_RULE, POSTCONDITION_RULE, loc_key, make, related


def check(run: ProofRun) -> list[Diagnostic]:
    by_entity: dict[str, list[Check]] = defaultdict(list)
    for c in run.checks:
        if c.entity:
            by_entity[c.entity].append(c)
    out = []
    for entity in sorted(by_entity):
        checks = sorted(by_entity[entity], key=loc_key)
        failed_inv = [c for c in checks
                      if c.rule == INVARIANT_RULE and c.unproved]
        proved_post = [c for c in checks
                       if c.rule == POSTCONDITION_RULE and c.proved]
        if not failed_inv or not proved_post:
            continue
        failed_post = [c for c in checks
                       if c.rule == POSTCONDITION_RULE and c.unproved]
        evidence = [
            f"{len(failed_inv)} unproved {INVARIANT_RULE} in {entity}",
            f"{len(proved_post)} {POSTCONDITION_RULE} reported proved in "
            f"{entity}",
        ]
        if failed_post:
            evidence.append(
                f"{len(failed_post)} {POSTCONDITION_RULE} already reported "
                f"unproved in {entity} (visible, not masked; context only)")
        disputed = [c for c in failed_inv + proved_post if c.disputed]
        if disputed:
            evidence.append(
                f"{len(disputed)} cited check(s) have a SARIF/.spark status "
                "disagreement: confidence lowered to medium")
        out.append(make(
            "SRD001",
            confidence=Confidence.MEDIUM if disputed else Confidence.HIGH,
            entity=entity,
            primary_location=failed_inv[0].location,
            explanation=(
                "GNATprove may assume the type invariant after checking it. "
                "Because the invariant check failed, postconditions proved "
                "afterward can be conditional on an inconsistent assumption: "
                "they may be masked. This is a structural warning. GNATprove "
                "output does not say which hypotheses each proof used, so no "
                "postcondition is claimed to be false."),
            recommendation=(
                "Fix the invariant failure first. Treat the postcondition "
                f"results of {entity} listed as potentially affected as "
                "potentially conditional, and re-check them after the "
                "invariant is restored."),
            evidence=tuple(evidence),
            related=tuple([related("failed", c) for c in failed_inv]
                          + [related("potentially affected", c)
                             for c in proved_post]
                          + [related("already unproved", c)
                             for c in failed_post]),
            data=(("proved_postconditions", len(proved_post)),
                  ("failed_invariants", len(failed_inv)))))
    return out
