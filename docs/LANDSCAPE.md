# SPARK Toolchain Opportunity Landscape

This document records why `spark-refine` is the recommended starting project rather than one of several adjacent ideas. The assessment is intentionally project-oriented rather than a claim about what is most important to formal methods in general.

## Decision criterion

The target is an **independent open-source project that materially reduces the cost of writing and maintaining proved SPARK code**, can deliver incremental value, and can coexist with/upstream into the existing AdaCore ecosystem rather than requiring a fork of GNATprove.

The dimensions below are qualitative:

- **Developer pain** — how much expert time the problem can consume.
- **Unfilled gap** — how little of the problem is already addressed by mature tooling.
- **Incremental feasibility** — whether useful value can ship before solving the whole research problem.
- **SPARK leverage** — how directly it improves SPARK proof work.

> **Update (Task 007).** This table was first written before any
> experiment. After Tasks 004–006, the project's core is **reusable proof
> architecture + proof diagnostics**, and generator-first with
> diagnostics later is no longer the plan. The assessments below reflect
> that. The original wording of the two changed rows is kept in the
> footnote.

| Opportunity | Developer pain | Unfilled gap | Incremental feasibility | SPARK leverage | Assessment |
|---|---:|---:|---:|---:|---|
| Refinement/model proof engineering | Very high | High | High | Very high | **Core, delivered as reusable SPARK proof libraries**; generation deferred |
| General invariant synthesis | Very high | High | Low/medium | Very high | High-value later research layer |
| Proof diagnostics/explanation | High | Medium | High | High | **Core, second pillar.** Proof-engineering diagnostics (SRD001–SRD003) built on GNATprove's foundations rather than reformatting them |
| Concurrency/temporal-model bridge | High | High | Low | High | Important but much larger semantic project |
| WCET/timing integration | Very high in hard RT | High | Low | Medium/high | Strategically important; separate large project |
| Certification/evidence generation | Medium/high | Medium | High | Medium | Useful downstream feature |
| IDE/editor experience | Medium | Medium/low | High | Medium | Build integrations, not another IDE |
| AI proof assistant | Potentially high | High | Medium | High | Should consume structured refinement data rather than be the foundation |

Original assessments (pre-Task 004):

* refinement/model proof engineering: "Recommended core";
* proof diagnostics: "Useful extension, but GNATprove already has
  substantial foundations".

## 1. Refinement/model proof engineering

### Existing foundation

SPARK already provides ghost code, contracts, functional/formal containers, abstraction boundaries, and state/refined contracts. Recent AdaCore examples use multiple model layers to make complex proofs tractable.

### Remaining gap

The developer still designs and maintains much of the glue linking concrete representation to abstract behavior. The 2025 functional-container paper describes proof by refinement through layers of models while noting that proof by refinement is not a dedicated native mechanism in SPARK.

### Why this is the best initial project

It has a narrow first experiment, a conservative trust model, and a clear success metric. We can support one representation, generate ordinary SPARK (original wording; now: provide ordinary SPARK as a library), and let GNATprove reject anything unsound. Each additional proven pattern adds independent value.

> **Update (Task 007).** The experiment ran as planned, and the trust
> argument held. The delivery mechanism changed: the fixed-pool pattern
> is a hand-written reusable SPARK generic that GNATprove re-proves per
> instance (`R = 10` local SLOC, down from 36), not generated SPARK.
> "Each additional proven pattern adds independent value" still
> describes the plan.

## 2. General loop-invariant and lemma synthesis

Automatic invariant generation would be extremely valuable. However, it is a substantially harder research problem if approached generally.

GNATprove already generates some frame conditions automatically. Its documentation also describes limits of the current heuristics, leaving meaningful room for improvement. The key distinction is that `spark-refine` can generate **pattern-derived invariants** from known semantics rather than attempting arbitrary program synthesis.

This makes invariant support a strong later feature:

```text
known refinement pattern
        +
known operation schema
        |
        v
candidate invariant
        |
    GNATprove
```

The tool can first emit candidates or generated contracts whose correctness is checked normally. General-purpose invariant synthesis can remain research work rather than an MVP dependency.

> **Update (Task 007): deferred.** Pattern-derived invariant generation
> is research/deferred (`docs/ROADMAP.md`). In the demonstrated fixed
> pool, the recurring loop invariants moved *inside* the proof-pattern
> library, so the application writes none.

## 3. Better proof diagnostics

Poor proof diagnostics are costly, but this is not an empty field. GNATprove already supports counterexamples in appropriate cases, source-localized messages, proof strategies, replay/caching workflows, and machine-readable output. SARIF creates a standard integration point.

A new diagnostics product that merely reformats prover output risks duplicating current work.

The valuable niche is **refinement-aware diagnosis**. Because `spark-refine` knows that an obligation came from “logical-to-physical index validity” or “append preserves prefix,” it can map a low-level failure back to the developer's model layer. That belongs naturally in this project after generation works. *(Historical framing; see the Task 005–006 update below. Diagnostics shipped without generation.)*

> **Evidence update (Tasks 001–003).** Several diagnostic needs have now
> appeared in two structurally different benchmarks, independent of any
> generator:
>
> * **Invariant masking.** Faults that break both the type invariant and a
>   functional postcondition are reported only at the invariant; the false
>   postcondition shows as proved. This happened in ring buffer B3/B4 and
>   in fixed pool P1/P5.
> * **Client-insufficient public contracts.** In the ring buffer, `Is_Full`
>   and `Is_Empty` had no model post. In the pool, clients could not derive
>   `Free_Count` arithmetic from `Length (Remove …)`.
> * **Mechanism choice.** `Dynamic_Predicate` fails where `Type_Invariant`
>   succeeds, with component-wise updates, in both benchmarks.
> * **Prover-portfolio fragility.** In the pool, only Alt-Ergo proves the
>   pigeonhole lemma.
>
> Whether diagnostics becomes the *primary* direction is still open; see
> the REVIEW decision in `docs/tasks/003-fixed-pool-proof-baseline.md`.
>
> **Update (Task 004).** A reusable SPARK generic library reduced the
> pool's per-instance proof support from 36 to 10 SLOC, giving **PIVOT**.
> The recurring proof knowledge fits in a library, so generation is not
> justified for this pattern, and diagnostics becomes the primary
> direction.
>
> The library did **not** remove any of the diagnostic needs above:
>
> * invariant masking is identical (L1/L5);
> * Alt-Ergo is still the only single prover that proves everything;
> * the invariant-removal baseline got noisier (2 → 8 failures), because
>   library contracts are guarded by `Is_Unique`;
> * GNATprove emits a misleading hint ("mention P in a precondition") when
>   the invariant is missing.
>
> See `docs/tasks/004-prefix-set-proof-library.md`.
>
> **Update (Tasks 005–006): diagnostics are no longer hypothetical.**
>
> * **SRD001–SRD003 exist:** invariant masking risk, client-only proof
>   gap, prover-portfolio dependency. They were built over GNATprove's
>   SARIF / `.spark` / `.ali` output, with no generated source map.
> * **Corpus:** 49 sanitized real GNATprove 16.1.0 result sets, and 137
>   fixture-based tests after Task 006.
> * **Fresh end-to-end validation:** one real GNATprove run per rule,
>   analyzed unsanitized in CI (`diagnostics-e2e`).
> * **Product:** installed as `spark-refine explain`, with stable
>   `format_version` 1 JSON for agents and CI.
>
> Measured results are per case on a small corpus, not accuracy rates:
>
> * SRD001 flagged all 9 structural masking-risk cases. 3 of those were
>   conservative warnings where the abstract postcondition was actually
>   true.
> * SRD002 claims a client-only *gap*, never a contract defect. A false
>   client assertion produces the same pattern.
> * SRD003 is limited to confidently matched checks.
>
> See `diagnostics/DIAGNOSTICS_METRICS.md`.
>
> The niche described above still holds. The value is not in
> reformatting prover output but in interpreting *proof-engineering
> structure*: masking, abstraction boundaries, prover dependence.
> "Knowing which generated obligation failed" turned out not to be
> required to get there.

## 4. Concurrency and temporal verification

SPARK's restrictions and analyses provide important race-freedom/tasking guarantees for supported tasking models, but system-level temporal properties can still require a different modeling discipline. A bridge between SPARK and TLA+/PlusCal or another temporal model could be valuable for protocols, scheduling, and lock-free algorithms.

Why it is not the first project:

- semantics must be mapped carefully between languages;
- equivalence between temporal model and implementation becomes the central soundness problem;
- concurrency examples are difficult benchmarks for a new proof-pattern library (originally: "for a new generator");
- it would serve a narrower subset of SPARK users initially.

A future `spark-refine` state-machine pattern could become a useful foundation for such a bridge.

## 5. WCET and timing-analysis integration

For hard-real-time software, functional proof is only part of correctness. Timing analysis is an important ecosystem opportunity. The open-source Bound-T project demonstrates that static WCET analysis for Ada is possible, but its public project status indicates limited ongoing development and platform/toolchain constraints. Commercial and specialist solutions also exist.

A modern open timing analyzer could arguably have enormous strategic value, but it is a different scale of undertaking:

- instruction timing is target-specific;
- modern caches, pipelines, speculation, memory systems, and multicore interference are difficult;
- compiler/code-generation details matter;
- validated hardware models become a maintenance burden;
- integration with linker maps, object code, and compiler versions is required.

For an independent repository intended to produce useful results early, this has much higher execution risk.

`spark-refine` should keep its architecture timing-aware—for example, library ghost code must not enter production behavior—but should not conflate functional refinement with WCET analysis.

## 6. Certification/evidence automation

Generating proof summaries, traceability, and evidence packs can save substantial assurance effort. It is also easier to build once proof artifacts have stable identifiers and machine-readable metadata.

This is an excellent downstream use of `spark-refine` metadata. It is not as directly connected to the day-to-day difficulty of getting a proof to succeed, so it should not be the initial mission.

## 7. IDE tooling

Ada Language Server and GNAT Studio already provide editor and project integration. The better approach is to make `spark-refine` expose clean commands and structured output, then add ALS/VS Code/GNAT Studio integration later.

Do not build another editor.

## 8. AI-first proof assistant

An AI agent can help interpret VCs, propose invariants, and write lemmas. But an AI-first project has two risks:

1. the output can be difficult to trust;
2. it may optimize for making a prover green instead of preserving the intended requirement.

A deterministic refinement core gives AI a much better substrate. The agent can manipulate a typed proof architecture whose authoritative requirements are clearly identified.

The recommended order was originally:

```text
refinement metadata
      -> deterministic generator
      -> GNATprove result
      -> structured diagnostics
      -> optional AI assistant
```

not the reverse.

> **Update (Task 007).** The principle stands: deterministic structure
> first, AI second. The substrate changed. Agents now consume:
>
> ```text
> reusable proof library (+ small application adapters)
>       -> GNATprove result
>       -> spark-refine explain --format json   (code/category/action/confidence)
>       -> optional AI agent
> ```
>
> See `docs/AGENT_INTEGRATION.md`.

## Recommendation

For the stated goal—making SPARK proven code easier to write and maintain—the best first repository is a **refinement/proof-engineering toolkit**, with `spark-refine` as a suitable working name.

The closest contender is a modern WCET project. If the goal were instead “fill the most strategically important missing hard-real-time capability regardless of scope,” WCET deserves a separate investigation. For a tractable open-source project that can demonstrate value in months rather than requiring extensive hardware/compiler research before the first useful result, refinement tooling is the stronger starting point.

The project's scope should be broader than “second-model generator” but narrower than “automatic SPARK verification” (original pre-experiment recommendation):

> **Automate recurring abstraction/refinement structure, preserve a small trust boundary, and build a reusable library of proof patterns.**

> **Update (Task 007).** The recommendation of a refinement /
> proof-engineering toolkit stands. The evidence changed *how* recurring
> structure is captured:
>
> * **reusable proof architecture:** reviewed SPARK generic libraries,
>   re-proved per instance by GNATprove, rather than generated source;
> * **proof diagnostics:** deterministic, read-only interpretation of
>   GNATprove results for humans and agents.
>
> The two are developed together, not "generator first, diagnostics
> later". See [ADR 0005](adr/0005-library-and-diagnostics-first.md).
