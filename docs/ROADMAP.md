# Roadmap

The roadmap is evidence-gated. Dates are intentionally omitted. Each
item should proceed only if the previous evidence shows value.

> **Status.** Task 007 replaced the actionable generator phase sequence
> with the current one below
> ([ADR 0005](adr/0005-library-and-diagnostics-first.md)). The evidence
> history and the original phases 0–10 are preserved in later sections.

## Current direction

Two pillars, with GNATprove as the proof authority:

1. **reusable SPARK proof-pattern libraries**, grown one validated
   pattern at a time;
2. **proof-aware diagnostics** over GNATprove output, for humans, CI and
   agents.

## Completed

| Step | Task(s) | Outcome |
|---|---|---|
| Experimental baseline and generator hypothesis | 001, 002 | manual ring buffers A and B: `P = 19` and `21`. Hypothesis weakened twice |
| Fixed-pool baseline | 003 | `P = 36`, all generic. **REVIEW** |
| Fixed-pool library experiment | 004 | `SPARK_Refine_Prefix_Sets`, `R = 10` (−72.2 %). **PIVOT** away from source generation |
| Diagnostics MVP | 005 | SRD001–SRD003 over SARIF / `.spark` / `.ali` (SRD001/SRD002 per run, SRD003 across single-prover runs), 49 real-result fixtures, fresh E2E gate |
| `explain` CLI productization | 006 | installed `spark-refine explain`, conservative discovery, `format_version` 1 JSON with `category`/`action`, `docs/AGENT_INTEGRATION.md` |

## Near term

* **Documentation and architecture realignment** (Task 007). Every
  current document describes the two-pillar product and its trust
  boundary. Generator documents are labelled historical/deferred.
* **Proof-run orchestration (possible, not committed).** An optional
  command that runs GNATprove and then explains, so that stale-result
  mistakes become harder. It must show the exact GNATprove command and
  never hide or alter its verdict. No such command exists today, and
  none is named yet. Today users run `gnatprove` themselves, then
  `spark-refine explain`.
* **Semantic diagnostic enrichment.** Libadalang-based identification of
  the call/callee and contract conjunct behind SRD002, and mapping
  failures to source abstractions. This is the main known limitation of
  the current diagnostics.

## Later

* **More reusable proof patterns where evidence warrants.** Each needs a
  benchmark showing that per-instance support is large and generic,
  independent validation instances, and measured proof-time effect.
* **Editor integration**: ALS / VS Code / GNAT Studio consuming the JSON,
  not a custom editor.
* **Stronger agent integration**: richer structured context for agents,
  still under the "do not weaken authoritative specifications" policy.
* **Certification and evidence outputs**: proof and trust summaries
  derived from GNATprove results. This is not a certification claim.
* **Broader toolchain compatibility**, for GNATprove / `.ali` versions
  beyond 16.1.0, validated before being claimed.

## Research / deferred

These items are not on the current path. Each would need new evidence.

* **Source generation** (manifest → IR → generated proof package). It was
  not justified for the demonstrated patterns. Revisit only if a pattern
  needs per-instance support that a generic library cannot carry.
* **Source annotations specifically for generation** (ADR 0004).
* **General invariant synthesis.** Pattern-derived invariants mostly
  live inside libraries now.
* **Concurrency / temporal bridge** (TLA+/PlusCal, SPSC queues).
* **WCET / timing integration.**
* **Upstream SPARK/GNATprove proposals** informed by real usage.

## Evidence history

> **Evidence so far (history preserved):**
>
> * **Task 001** (ring buffer A: `P = 19`) weakened the generator
>   hypothesis.
> * **Task 002** (ring buffer B: 21) weakened it again.
> * **Task 003** (fixed pool: 36, all generic) gave **REVIEW**.
> * **Task 004** decided library vs. generator: a hand-written reusable
>   generic (`proof_patterns/`) left `R = 10` per-instance SLOC, giving
>   **PIVOT**.
>
> The historical phases (see "Historical: original phase plan" below)
> were written before that evidence.
>
> * **Phase 2** (circular-sequence generator) and **Phase 3** are **not
>   pursued** on current evidence.
> * The project proceeds as:
>   1. a reusable SPARK proof-pattern library (grown one validated pattern
>      at a time, each with independent validation instances);
>   2. refinement/specification diagnostics, i.e. Phase 7 brought forward
>      (next: invariant-masking and contract-sufficiency diagnosis, as
>      proposed in `docs/tasks/004-prefix-set-proof-library.md`);
>   3. optional thin convenience tooling around the libraries.
>
> **Task 005** started item 2 with `diagnostics/`, a deterministic
> analyzer over GNATprove SARIF/.spark. It has three rules:
>
> * SRD001: invariant masking risk. All 9 structural masking-risk cases
>   were detected, and all 6 ablation-confirmed secondary failures were
>   among them.
> * SRD002: client-only proof gap; the public abstraction may be
>   insufficient. Confidence is medium or low, and the rule makes no
>   contract-deficiency claim.
> * SRD003: prover-portfolio dependency, for confidently matched checks
>   only.
>
> See `docs/tasks/005-proof-diagnostics-mvp.md` and
> `diagnostics/DIAGNOSTICS_METRICS.md`.
>
> **Task 006** productized the diagnostics as the installable Python
> command `spark-refine` (`pip install ./diagnostics`). It adds:
>
> * `spark-refine explain` with conservative result-set discovery;
> * `analyze` kept as an alias;
> * stable `category`/`action` fields and a derived `summary` in the JSON;
> * `docs/AGENT_INTEGRATION.md`.
>
> It adds no rule and does not use Libadalang. The `spark_refine explain`
> of Phase 7 below is therefore the Python `spark-refine explain` (with a
> hyphen), not a command of the Ada bootstrap executable. See
> `docs/tasks/006-explain-cli-productization.md`.
>
> **Task 007** realigned the documentation with this direction. It adds
> ADR 0005, rewrites the vision, architecture, MVP and roadmap, and
> labels the generator documents historical/deferred. It changes no
> behavior.

## Historical: original phase plan (generator-first)

> **Status: historical/deferred.** These are the original phases 0–10,
> kept unchanged except that headings are demoted one level. They are no
> longer the actionable plan:
>
> * Phases 0, 1 and the manual parts of 4–5 were carried out as
>   experiments (Tasks 001–004).
> * Phase 7 was brought forward, without generation, as Tasks 005–006.
> * Phases 2, 3 (as a generator dependency), 4's `diff`/`check`, 6 and 8
>   are deferred.
> * Phases 9–10 continue in the "Later" section above, in a different
>   form.

### Phase 0 — repository and research baseline

Deliverables:

- problem statement;
- landscape analysis;
- trust policy;
- architecture decisions;
- example manifest;
- CLI skeleton;
- benchmark design.

This bootstrap repository is Phase 0.

### Phase 1 — manual proof benchmark

Build and prove the circular-buffer baseline by hand.

Deliverables:

- complete SPARK implementation;
- GNATprove configuration;
- proof-support inventory;
- negative fixtures;
- baseline metrics.

No generator work should outrun this benchmark.

### Phase 2 — circular-sequence generator

Implement:

- TOML parsing;
- refinement IR;
- validation;
- deterministic source generation;
- first pattern;
- golden tests;
- forbidden-assumption scanner;
- proof CI.

Exit criterion: generated fixture reaches the same proof result as baseline.

### Phase 3 — semantic Ada integration

Add Libadalang.

Capabilities:

- resolve target entities;
- validate types/visibility;
- locate source declarations;
- detect conflicts;
- improve diagnostics;
- remove fragile string-based assumptions.

### Phase 4 — refactor support

Add:

```text
spark_refine diff
spark_refine check
```

Perform representation B benchmark and client-proof stability test.

### Phase 5 — second proof pattern

Preferred: fixed pool with a set-based abstract model.

This phase tests whether the core IR and pattern interface generalize beyond sequences.

If major architecture changes are required, make them now before promising third-party plugin stability.

### Phase 6 — source annotations

Prototype `pragma/aspect Annotate` syntax after real manifests reveal the stable concepts.

Goals:

- colocate role declarations with representation;
- keep project-level policy in TOML;
- preserve manifest-only mode.

### Phase 7 — proof-aware diagnostics

Ingest GNATprove machine-readable output.

Implement:

```text
spark_refine explain
```

Map VCs to:

- user requirement;
- refinement layer;
- pattern rule;
- generated declaration;
- likely representation concept.

### Phase 8 — pattern-derived invariant suggestions

Generate or suggest invariants from known pattern semantics.

Start with deterministic cases such as loops that copy a logical prefix or scan bounded storage.

Do not begin with general invariant synthesis.

### Phase 9 — editor integration

Expose structured JSON/LSP-friendly diagnostics. Integrate with existing Ada editor infrastructure instead of building a custom editor.

### Phase 10 — optional AI agent

Only after the deterministic architecture is stable.

Agent tasks may include:

- explaining failed obligations;
- proposing application-specific invariants;
- selecting existing lemmas;
- suggesting a missing refinement layer;
- generating a candidate representation mapping.

Guardrails must distinguish proof-support changes from requirement weakening.

### Long-term research branches

Potential independent tracks:

- concurrency/state-machine refinement;
- TLA+/PlusCal linkage;
- DMA/ownership-ring patterns;
- assurance/evidence reports;
- WCET metadata correlation;
- upstream SPARK language/tool proposals informed by real usage.
