# Original README (bootstrap design, pre-Task 006)

> **Historical document.** This is the repository README as it stood
> before Task 006, preserved verbatim below the line. It describes the
> original *source-generation* hypothesis, which Tasks 001-004 tested and
> deliberately deprioritized (Task 004 decision: PIVOT). See the current
> [`README.md`](../../README.md) and [`docs/ROADMAP.md`](../ROADMAP.md).
> Relative links below are relative to the repository root.

---

# spark-refine

**Proof-engineering automation for SPARK refinement models.**

> Status: design bootstrap / pre-alpha. The repository currently defines the problem, architecture, trust model, MVP, proof-pattern strategy, benchmarks, and a minimal CLI skeleton. It does **not** yet generate production proof artifacts.

`spark-refine` is an open-source project intended to reduce the amount of repetitive proof engineering required to connect a clean mathematical model to an efficient SPARK implementation.

The central idea is simple:

> Let developers state behavior at the abstraction level that makes the requirement obvious, describe how a concrete real-time representation implements that abstraction, and generate as much of the mechanical refinement scaffolding as possible. GNATprove remains the proof authority.

A bounded circular buffer illustrates the problem. Production code wants fixed storage, bounded execution, explicit indices, no allocation, and predictable memory behavior. A specification wants to say something much simpler:

```text
Push(X):  Model' = Model & X
Pop:      Model' = Tail(Model)
```

Bridging those two views often requires ghost model functions, representation predicates, index-mapping functions, preservation lemmas, refined contracts, and loop invariants. Much of that work is conceptually repetitive across projects.

`spark-refine` aims to make the **abstract contract** the stable interface and automate the **proof plumbing** beneath it.

## Why this project

The project is motivated by three observations from the SPARK ecosystem:

1. SPARK already has the right proof ingredients: ghost code, functional/formal containers, contracts, package abstraction, `Refined_State`, and `Refined_Post`.
2. Hard proofs commonly benefit from one or more model layers. Recent AdaCore material shows complex container proofs using several layers of abstraction and explicit refinement links.
3. Those links remain largely hand-authored. The high-value opportunity is therefore not another prover; it is tooling that makes refinement structure easier to declare, generate, inspect, reuse, and maintain.

The intended trust relationship is deliberately conservative:

```text
Developer intent + implementation
              |
              v
         spark-refine
              |
     generated SPARK code
              |
              v
          GNATprove
              |
        Why3 / provers
```

The generator is not the proof authority. Generated claims must be ordinary, reviewable SPARK that GNATprove proves. The default project policy forbids generated unchecked assumptions or axioms.

## What success looks like

For a supported representation pattern, a developer should be able to:

1. Write the real implementation.
2. Write the high-level behavioral contract in SPARK.
3. Declare a small mapping between implementation fields and a known abstract pattern.
4. Run `spark_refine generate`.
5. Run GNATprove and work primarily on genuinely application-specific proof obligations rather than rebuilding generic circular-index, representation-preservation, and model-equivalence machinery.

The first quantitative target is to reduce **developer-authored proof-support code by at least 50%** for a bounded circular-buffer benchmark while preserving complete GNATprove verification and keeping the generated output readable.

A second target is representation-refactor resilience: changing a buffer from `First + Length` to `Head + Tail + Count` should leave the public abstract behavior unchanged and concentrate proof changes in the representation mapping/refinement layer.

## Scope

The initial project focuses on deterministic, reviewable refinement generation for bounded real-time data structures. The first pattern is a circular sequence. Follow-on candidates include fixed pools, free lists, bitmap allocators, state machines, bounded maps, and eventually SPSC/DMA descriptor rings.

The project is intentionally **not**:

- a replacement for GNATprove, Why3, or SPARKlib;
- a new SPARK dialect;
- an AI system that declares code correct;
- a WCET analyzer;
- a general automatic theorem prover;
- a generator of unchecked assumptions.

AI-assisted proof suggestions, proof-diagnostic integration, IDE support, and timing-analysis integrations are possible later layers, but the core must first demonstrate deterministic value without requiring AI.

## Proposed workflow

The design uses an external manifest for the MVP so the idea can be tested without modifying the Ada/SPARK language or source parser:

```toml
format_version = 1

[[refinement]]
name = "queue_contents"
target = "Ring_Buffer.Buffer"
pattern = "circular_sequence"
model_function = "Model"

[refinement.representation]
storage = "Content"
first = "First"
length = "Length"
capacity = "Max_Size"
index_origin = 1

[refinement.generation]
backend = "derived"
emit_model_mapping = true
emit_representation_predicate = true
emit_lemmas = true
emit_refined_contracts = true
```

Longer term, metadata should be colocated with source using standard Ada tooling mechanisms such as `pragma Annotate`/`aspect Annotate`, with Libadalang used for semantic source analysis. The external manifest should remain available for generated code and projects that prefer source-neutral configuration.

## Planned CLI

```text
spark_refine init -P project.gpr --unit Ring_Buffer
spark_refine validate
spark_refine generate
spark_refine diff
spark_refine check

# later
spark_refine explain
spark_refine migrate
```

`check` is intended for CI: regenerate into a temporary directory, compare deterministic output, and fail on drift.

`explain` is a later integration point for GNATprove's machine-readable proof output (including `.spark`/SARIF data) so failures can be mapped back to the abstraction/refinement layer that produced them.

## Repository map

```text
README.md                       project overview
CONTRIBUTING.md                 contribution workflow
SECURITY.md                     trust/soundness issue policy
src/                            minimal CLI bootstrap
docs/MOTIVATION.md              detailed problem statement
docs/LANDSCAPE.md               alternative-project gap analysis
docs/VISION.md                  long-term product vision
docs/ARCHITECTURE.md            architecture and generation model
docs/SPEC.md                    proposed user-facing semantics
docs/MANIFEST.md                MVP manifest design
docs/TRUST_MODEL.md             soundness and trust boundary
docs/PROOF_PATTERNS.md          reusable refinement-pattern design
docs/MVP.md                     first implementation scope
docs/BENCHMARKS.md              validation experiments
docs/METRICS.md                 success/failure metrics
docs/ROADMAP.md                 staged development plan
docs/INTEGRATION.md             GNATprove/SPARKlib/Libadalang/Alire plan
docs/RESEARCH.md                ecosystem research and references
docs/FAQ.md                     design questions
docs/adr/                       architecture decision records
examples/ring_buffer/           first design fixture
```

The first implementation task is fully specified in [`docs/tasks/001-manual-ring-buffer-baseline.md`](docs/tasks/001-manual-ring-buffer-baseline.md).

## Near-term milestones

The project should earn the right to expand. The first release is not “support every SPARK program.” It is one convincing experiment:

**Milestone 0 — Baseline.** Hand-prove a small bounded circular buffer, record all developer-authored model/lemma/invariant code, GNATprove results, proof time, and maintenance behavior.

**Milestone 1 — Deterministic generator.** Parse one manifest pattern and generate reviewable package-level proof scaffolding for that exact representation.

**Milestone 2 — Equivalent proof.** Demonstrate that stock GNATprove proves the generated version without generated assumptions.

**Milestone 3 — Refactor benchmark.** Change the implementation representation while preserving the abstract contract and measure how much proof work is localized.

**Milestone 4 — Second pattern.** Add a sufficiently different structure (probably fixed pool or bitmap allocator) to prove the architecture is not ring-buffer-specific.

Only after those milestones should the project pursue invariant suggestions, source annotations, IDE integration, or AI-assisted repair.

## Design principles

- **Proof authority stays with GNATprove.**
- **No hidden axioms.** Generated claims must be proved or come from explicitly reviewed foundations.
- **Readable generated Ada.** A human must be able to audit the proof structure.
- **Deterministic output.** Same inputs produce byte-stable output where practical.
- **Abstract contracts are primary.** Representation details should not leak into client specifications.
- **Generated code is disposable.** Regeneration, not hand editing, is the maintenance path.
- **Measure proof effort.** The project exists to save human work, not merely move lines between files.
- **Start narrow.** A small proven pattern library is more valuable than broad unreliable automation.

## Research basis

See [`docs/RESEARCH.md`](docs/RESEARCH.md) for references. Particularly relevant are recent AdaCore materials on functional containers, proof by refinement, multiple model layers, loop-invariant generation, machine-readable GNATprove output, and SPARK's existing state-refinement facilities.

The current landscape assessment is summarized in [`docs/LANDSCAPE.md`](docs/LANDSCAPE.md): for an independent open-source project specifically aimed at making **writing proved SPARK code cheaper and easier**, refinement/proof-engineering automation appears to be the strongest tractable gap. WCET integration is strategically important for hard real-time systems but is a much larger, target-specific problem and does not directly address the recurring proof-model duplication motivating this work.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
