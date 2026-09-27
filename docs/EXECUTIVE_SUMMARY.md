# Executive Summary

> **Status (Task 007): the problem statement is current, the proposal is
> not.** The problem analysis below still stands. The proposed solution,
> "generates ordinary SPARK proof artifacts from a small, explicit
> refinement description", was tested in Tasks 001–004 and deprioritized.
>
> **Current summary.** `spark-refine` is a proof-engineering toolkit for
> SPARK. It combines reusable, GNATprove-verified proof patterns with
> proof-aware diagnostics for humans and AI agents. GNATprove remains the
> proof authority.
>
> * **Reusable proof patterns.** On the fixed pool, the SPARK generic
>   `SPARK_Refine_Prefix_Sets` cut per-instance proof support from 36 to
>   10 SLOC (−72.2 %). The public API and client proof were unchanged, and
>   no assumptions were added.
> * **Diagnostics.** `spark-refine explain` interprets GNATprove's
>   SARIF / `.spark` / `.ali` output:
>   * SRD001, invariant masking risk;
>   * SRD002, client-only proof gap;
>   * SRD003, prover-portfolio dependency.
>
>   It emits stable JSON for agents and is read-only.
>
> The falsifiable hypothesis in "The first falsifiable hypothesis" was
> measured. The circular buffer needed only 19–21 SLOC of support, and
> for the pool a library, not generated source, delivered the reduction.
> See [ADR 0005](adr/0005-library-and-diagnostics-first.md),
> `docs/VISION.md` and `docs/ARCHITECTURE.md`. The original text follows
> unchanged.

## The problem

SPARK makes it possible to prove strong properties about production Ada code, but production representations and proof representations optimize for different things.

A hard-real-time implementation often optimizes for:

- bounded memory;
- bounded execution time;
- static allocation;
- cache/locality behavior;
- hardware-compatible layout;
- lock-free or low-contention synchronization;
- explicit ownership and state transitions.

A proof specification often wants:

- sequences rather than circular arrays;
- mathematical sets rather than bitmaps;
- maps rather than hash tables;
- abstract states rather than packed words;
- algebraic operations rather than index manipulation.

The result is frequently a second view of the same state: a ghost model or one or more intermediate models. That abstraction is valuable—it is often what makes the proof understandable—but the developer pays a recurring cost to connect it to the implementation.

The expensive part is not just defining `Model`. It is maintaining the relation between the model and the implementation across every mutating operation and every representation change. A serious refinement proof may require:

- a model function;
- a representation predicate;
- logical-to-physical index mappings;
- model validity properties;
- frame/preservation properties;
- operation-specific refinement contracts;
- lemmas about wraparound, slices, membership, or ownership;
- loop invariants that preserve the relation;
- intermediate model layers when the concrete-to-abstract jump is too difficult for automated provers.

## The proposal

`spark-refine` is a proof-engineering automation layer for SPARK. It does **not** attempt to prove programs independently. It generates ordinary SPARK proof artifacts from a small, explicit refinement description and a library of reviewed proof patterns.

The key separation is:

```text
WHAT the component means                 HOW it is represented
------------------------                 ---------------------
Public SPARK contract                    Bounded arrays
Functional container model              Head/tail indices
State-machine semantics                 Bitmaps
                                        Pools
                                        Packed records
                 \                       /
                  \                     /
                   +--- refinement -----+
                         tooling
                            |
                    generated SPARK
                            |
                         GNATprove
```

The project's first pattern is a bounded circular sequence. If that experiment succeeds, the same architecture can support additional structures.

## Why this is a strong SPARK-toolchain opportunity

The surrounding toolchain already addresses many tempting adjacent problems:

- GNATprove has proof diagnostics and counterexamples.
- GNATprove can emit machine-readable proof information.
- GNATprove supports proof replay/caching workflows.
- GNATprove already generates some loop frame conditions.
- SPARK already has functional/formal containers.
- SPARK already has state refinement mechanisms such as `Refined_State` and `Refined_Post`.
- Ada has mature semantic tooling through Libadalang.

What is still notably manual is the **proof-engineering structure between layers of models**. Recent AdaCore material itself demonstrates multi-layer model/refinement proofs for complex containers. A 2025 paper on SPARK functional containers describes proof by refinement via multiple model layers while noting that it is not natively supported as a dedicated SPARK mechanism.

That makes refinement automation attractive for three reasons:

1. **It attacks real human effort rather than duplicating an existing prover feature.**
2. **It can be built outside GNATprove with a small trust footprint.**
3. **It can deliver value incrementally, one reusable representation pattern at a time.**

## The most important product decision

The project should not promise to “eliminate the second model.” The second model is often exactly the right abstraction.

The promise is instead:

> **Make models cheap to connect, cheap to maintain, and reusable across common implementation patterns.**

That distinction prevents the project from becoming a fragile automatic-proof system.

## The first falsifiable hypothesis

For a bounded circular buffer with a meaningful public abstract contract, a developer currently writes substantial support code whose purpose is generic rather than application-specific.

The hypothesis is:

> A declarative pattern description plus generated SPARK can remove at least half of that developer-authored support code while preserving a zero-unproved-VC GNATprove result and keeping generated proof code readable.

The benchmark must include a representation refactor. If the tool saves lines only during initial creation but becomes worse to maintain, it has failed.

## Long-term opportunity

If the pattern library becomes useful, `spark-refine` can evolve from generator to proof-engineering platform:

- source annotations parsed with Libadalang;
- reusable lemma libraries;
- invariant-candidate generation;
- GNATprove-result mapping to abstraction layers;
- IDE navigation between generated obligations and user declarations;
- AI agents operating over structured proof metadata rather than guessing from diagnostics;
- optional evidence reports for reviews and assurance cases;
- timing/WCET metadata integration without conflating functional proof with timing analysis.

The foundation, however, remains deterministic refinement generation that can be audited and proved by existing SPARK tooling.
