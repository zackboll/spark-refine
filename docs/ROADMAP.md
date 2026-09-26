# Roadmap

The roadmap is evidence-gated. Dates are intentionally omitted; each phase should proceed only if the previous one demonstrates value.

## Phase 0 — repository and research baseline

Deliverables:

- problem statement;
- landscape analysis;
- trust policy;
- architecture decisions;
- example manifest;
- CLI skeleton;
- benchmark design.

This bootstrap repository is Phase 0.

## Phase 1 — manual proof benchmark

Build and prove the circular-buffer baseline by hand.

Deliverables:

- complete SPARK implementation;
- GNATprove configuration;
- proof-support inventory;
- negative fixtures;
- baseline metrics.

No generator work should outrun this benchmark.

## Phase 2 — circular-sequence generator

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

## Phase 3 — semantic Ada integration

Add Libadalang.

Capabilities:

- resolve target entities;
- validate types/visibility;
- locate source declarations;
- detect conflicts;
- improve diagnostics;
- remove fragile string-based assumptions.

## Phase 4 — refactor support

Add:

```text
spark_refine diff
spark_refine check
```

Perform representation B benchmark and client-proof stability test.

## Phase 5 — second proof pattern

Preferred: fixed pool with a set-based abstract model.

This phase tests whether the core IR and pattern interface generalize beyond sequences.

If major architecture changes are required, make them now before promising third-party plugin stability.

## Phase 6 — source annotations

Prototype `pragma/aspect Annotate` syntax after real manifests reveal the stable concepts.

Goals:

- colocate role declarations with representation;
- keep project-level policy in TOML;
- preserve manifest-only mode.

## Phase 7 — proof-aware diagnostics

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

## Phase 8 — pattern-derived invariant suggestions

Generate or suggest invariants from known pattern semantics.

Start with deterministic cases such as loops that copy a logical prefix or scan bounded storage.

Do not begin with general invariant synthesis.

## Phase 9 — editor integration

Expose structured JSON/LSP-friendly diagnostics. Integrate with existing Ada editor infrastructure instead of building a custom editor.

## Phase 10 — optional AI agent

Only after the deterministic architecture is stable.

Agent tasks may include:

- explaining failed obligations;
- proposing application-specific invariants;
- selecting existing lemmas;
- suggesting a missing refinement layer;
- generating a candidate representation mapping.

Guardrails must distinguish proof-support changes from requirement weakening.

## Long-term research branches

Potential independent tracks:

- concurrency/state-machine refinement;
- TLA+/PlusCal linkage;
- DMA/ownership-ring patterns;
- assurance/evidence reports;
- WCET metadata correlation;
- upstream SPARK language/tool proposals informed by real usage.
