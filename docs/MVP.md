# Minimum Viable Product

## MVP objective

Prove or disprove one narrow hypothesis:

> For a conventional bounded circular buffer, can a small refinement declaration generate enough correct SPARK proof scaffolding to materially reduce human-authored proof support without adding trust assumptions?

The MVP is successful even if the answer is “only for representation X under constraints Y,” provided the result is measured and honest.

## Out of scope

The MVP does not need:

- arbitrary Ada parsing by hand;
- multiple patterns;
- VS Code integration;
- AI assistance;
- automatic arbitrary loop-invariant synthesis;
- concurrency;
- atomics/memory-order reasoning;
- WCET analysis;
- certification documents;
- dynamic third-party pattern plugins.

## Phase M0 — hand-written baseline

Create a ring-buffer example with:

- capacity fixed by a generic or constant;
- private bounded storage;
- `First + Length` representation;
- `Push` and `Pop`;
- an abstract sequence model;
- complete GNATprove proof;
- no unchecked assumptions.

Record which lines exist solely for proof support.

Classify them:

```text
model construction
representation predicate
index helpers
lemmas
loop invariants
operation refinement
other
```

This baseline is mandatory. We cannot claim to reduce proof effort without knowing what the manual proof costs.

## Phase M1 — manifest and IR

Implement:

```text
spark_refine validate
spark_refine generate
```

Parse TOML with a maintained Ada TOML library rather than building a custom parser.

The generator may initially require explicit fully-qualified entity names and a deliberately small representation schema.

## Phase M2 — semantic source resolution

Integrate Libadalang so the validator can confirm that configured entities exist and have compatible declarations.

Do not infer semantics from raw text/regex.

## Phase M3 — first generated proof layer

Generate a proof package containing at minimum:

- logical-to-physical mapping;
- mapping-in-range property;
- model-length relation;
- representation validity predicate;
- standard append/remove helper lemmas that the baseline proves need.

Avoid generating every imaginable lemma. Measure which ones eliminate real manual work.

## Phase M4 — stock GNATprove gate

CI proves the fixture with supported GNATprove.

Pass criteria:

```text
unproved generated VCs = 0
forbidden generated assumptions = 0
run-time check obligations for generated executable code = 0 or not applicable
```

Ghost code can be computationally inefficient but must obey SPARK proof rules.

## Phase M5 — refactor benchmark

Change the concrete representation to `Head + Tail + Count` or another meaningful variant while preserving the public model/contracts.

Measure:

- user-written lines changed;
- generated lines changed;
- manual proof artifacts rewritten;
- proof runtime;
- public client proof changes.

The ideal result is that client proofs do not change and most proof churn is generated.

## CLI behavior for the MVP

```text
spark_refine --version
spark_refine validate [--manifest FILE]
spark_refine generate [--manifest FILE] [--out DIR]
spark_refine check [--manifest FILE]
```

`check` should eventually:

1. validate;
2. generate to a temporary location;
3. compare output to the checked-in/generated directory;
4. fail on drift.

Running GNATprove from `check` can be added after the generator is stable.

## MVP completion definition

The MVP is complete only when a report answers:

- How many proof-support lines did the manual baseline require?
- How many remain user-authored with `spark-refine`?
- Did all generated obligations prove?
- How much generated code was emitted?
- Was the generated code understandable in review?
- What changed during representation refactor?
- Did proof time regress materially?
- Which parts could not be automated and why?

A generator that emits 1,000 opaque lines to save 30 transparent lines is not automatically a success.
