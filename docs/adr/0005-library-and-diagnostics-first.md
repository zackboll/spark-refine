# ADR 0005: Prefer reusable proof libraries and diagnostics over a generator-first architecture

Status: Accepted (Task 007, recording the decision taken in Tasks 004–006)

Supersedes the *implementation priority* of ADR 0003 and ADR 0004. Their
rationale is kept as history. ADR 0001 and ADR 0002 remain in force.

## Context

The project began with a generator-first hypothesis:

```text
manifest -> refinement IR -> source generator -> generated SPARK proof
scaffolding -> GNATprove
```

The claim was that the mechanical support connecting a concrete
representation to its abstract model is big and repetitive enough to be
worth generating from a small declaration. That support includes model
adapters, representation invariants, lemmas and loop invariants. See
`docs/history/ORIGINAL_README.md`, `docs/SPEC.md` and `docs/MANIFEST.md`.

## Evidence

All numbers were measured on fully proved benchmarks with the pinned FSF
GNAT / GNATprove / SPARKlib 16.1.0 toolchain.

| Task | Result | Effect on the hypothesis |
|---|---|---|
| 001 | Ring buffer A (`First + Length`): mechanical support `P = 19` SLOC, 0 lemmas | weakened |
| 002 | Ring buffer B (`Head + Tail + Count`): `P = 21`. The redundant state needed only a 2-line `Type_Invariant` | weakened again |
| 003 | Fixed pool (free-index stack → set): `P = 36`, all of it generic | **REVIEW** |
| 004 | Hand-written reusable generic `SPARK_Refine_Prefix_Sets` (`L = 98`). Per-instance residual `R = 10` SLOC, a 72.2 % local reduction. Public API and client proof unchanged | **PIVOT** away from source generation |
| 005 | Deterministic diagnostics over real GNATprove output: SRD001 invariant masking risk, SRD002 client-only proof gap, SRD003 prover-portfolio dependency. 49 real-result fixtures | diagnostics are viable |
| 006 | Installed `spark-refine` CLI: `spark-refine explain`, conservative result discovery, stable `format_version` 1 JSON with `category`/`action` metadata for agents | diagnostics are usable |

The recurring proof knowledge in the demonstrated patterns fits in an
ordinary SPARK generic. What remains per instance, such as generic
actuals and a one-call model adapter, is about as small as a manifest
declaration would be. Generation would therefore add a trusted-looking
tool layer for little saved work.

## Decision

The current architecture prioritizes two pillars:

1. **Reusable SPARK proof-pattern libraries.** These are reviewed,
   GNATprove-verified generics that encode proof knowledge once.
2. **Proof-aware diagnostics.** These are read-only, deterministic
   interpretation of GNATprove's SARIF / `.spark` / `.ali` output, for
   humans and AI agents.

GNATprove remains the only proof authority.

Source generation, the manifest, the refinement IR and source
annotations for generation are **deferred**. They are not justified on
current evidence and will be reconsidered only if a future benchmark
shows a pattern whose per-instance support a library cannot absorb.

## Consequences

Positive:

* a smaller trust and product surface, with no generator whose output
  must be reviewed;
* ordinary SPARK generics that users can read, instantiate and prove
  with stock tools;
* GNATprove remains the authority, because every library instance is
  re-proved;
* less application-owned proof plumbing (36 → 10 SLOC on the fixed
  pool);
* a stable diagnostics interface (`spark-refine explain --format json`)
  for humans, CI and agents.

Tradeoffs:

* GNATprove re-proves generic proof bodies **per instance**. Authoring
  is reused; proof execution is not (fixed pool: 136 → 161 checks; gate
  wall time ≈ 1.9 s → 2.2 s, max prover steps 7 553 → 294);
* diagnostics are deliberately conservative. They report risks and gaps,
  not causes, and SRD002 is skipped when `.ali` dependency data is
  unavailable or unsupported;
* semantic source understanding is still limited. Without Libadalang,
  diagnostics cannot yet name a callee or a contract conjunct;
* libraries cover only representation families that have been
  validated. Today that is one: unique prefix → functional set.

## Revisit when

* a validated pattern needs substantial per-instance support that a
  generic cannot carry (e.g. per-operation proof code that depends on
  application-specific structure); or
* several libraries share instantiation boilerplate large enough that
  thin generation would clearly pay for its trust cost.
