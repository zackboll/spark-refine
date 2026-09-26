# Vision

## One sentence

Make the abstraction layer of a SPARK proof a first-class, reusable engineering artifact rather than bespoke ghost-code plumbing recreated for every implementation.

## Developer experience we want

Consider a bounded queue. The developer should be able to read its public specification and see only domain behavior:

```ada
procedure Push (B : in out Buffer; E : Element)
with
  Pre  => Model (B)'Length < Capacity,
  Post => Model (B) = Model (B)'Old & E;
```

The private implementation can remain optimized:

```text
Content[1 .. N]
First
Length
```

The developer then declares that this representation is an instance of a `circular_sequence` refinement pattern. `spark-refine` generates the mechanical proof layer.

The ideal interaction is:

```text
$ spark_refine validate
Refinement queue_contents: valid
Pattern circular_sequence: compatible
Concrete roles: storage=Content, first=First, length=Length
Abstract model: Model

$ spark_refine generate
Generated 6 ghost helpers
Generated 4 representation properties
Generated 8 standard lemmas
Generated 2 operation refinement helpers
No assumptions generated

$ gnatprove -P queue.gpr ...
...
```

When the proof fails, the user should eventually see something like:

```text
Refinement failure: queue_contents / append-preserves-prefix
GNATprove obligation: ...
Likely concrete boundary: First/Length wraparound
Generated helper: Queue_Contents_Proof.Lemma_Append_Wrap
```

The tool should expose structure, not hide it.

## Stable requirements, replaceable representations

A high-level model should be a component's semantic API for proofs.

```text
                   clients
                      |
                 contracts
                      |
                abstract model
               /      |       \
              /       |        \
         repr A     repr B    repr C
```

This mirrors ordinary software abstraction. Clients should not need to understand a container's private layout. Proof clients should not need to understand it either.

## A community library of refinement knowledge

Long term, a `spark-refine-patterns` library can encode reusable proof knowledge:

- circular sequence;
- bounded vector;
- fixed object pool;
- free list;
- bitmap set/allocator;
- bounded map;
- state machine;
- priority structure;
- ownership table;
- descriptor ring.

Patterns should be versioned and testable. Each should ship with:

- formal meaning;
- required representation roles;
- generated artifacts;
- supported operation schemas;
- examples;
- negative tests;
- proof benchmarks;
- compatibility notes for SPARK/GNATprove versions.

## Refactoring as a first-class proof operation

A proof tool should expect implementations to change.

Future commands should explicitly help with representation evolution:

```text
spark_refine diff
spark_refine migrate
```

A diff should describe semantic effects:

```text
Representation role changed:
  length: Count -> derived(Head, Tail, Is_Full)

Affected generated obligations:
  logical_length_valid
  empty_equivalence
  full_equivalence

Public abstract contracts changed: none
```

This is more useful than treating every generated-file diff as equally meaningful.

## Integration vision

The project should be a good citizen of the Ada/SPARK ecosystem:

- Alire for distribution;
- GPR projects for build integration;
- Libadalang for semantic inspection;
- SPARKlib functional containers for abstract models where appropriate;
- GNATprove as proof authority;
- `.spark`/SARIF ingestion for diagnostics;
- `Annotate` metadata for optional source-local declarations;
- editor integration through existing Ada tooling instead of a custom IDE.

## What maturity could look like

A mature release might support three levels of automation.

### Level 1 — Structural generation

The user chooses a known pattern and the tool generates names, model mapping, predicates, and standard lemmas.

This is deterministic and should be the first production-quality level.

### Level 2 — Proof-guided suggestions

The tool reads GNATprove output and proposes missing generated or user invariants based on the known refinement layer. Suggestions are explicit and reviewable.

### Level 3 — Agentic proof engineering

An optional agent can iterate over failed proof obligations, but is constrained by policy:

- public requirements cannot be weakened silently;
- assumptions cannot be introduced silently;
- generated changes are categorized;
- GNATprove performs final checking;
- the developer receives a semantic diff.

The deterministic pattern system makes this far safer than unconstrained source editing.
