# Vision

> **Status.** Rewritten in Task 007 to match the evidence-backed
> direction ([ADR 0005](adr/0005-library-and-diagnostics-first.md)).
> The original generator-first vision is preserved at the end of this
> file as history.

## One sentence

**spark-refine is a proof-engineering toolkit for SPARK. It combines
reusable, GNATprove-verified proof patterns with proof-aware diagnostics
for humans and AI agents. GNATprove remains the proof authority.**

## The problem, restated after Tasks 001–006

The abstraction layer of a SPARK proof connects a concrete
representation to an abstract model. It includes model adapters,
representation invariants, lemmas and loop invariants. Many projects
rebuild it by hand, and when a proof fails, the low-level check output
often hides which layer is at fault.

The project first tried to *generate* that layer. The experiments showed
two things instead:

* the recurring part is best captured once, in **reviewed SPARK generic
  libraries** that GNATprove re-proves per instance;
* the most valuable remaining help is **understanding proof failures**:
  which layer failed, whether a green result can be trusted, and whether
  a failure is about the prover rather than the program.

## Developer experience we want

Task 019 tested the limits of library integration: manual P=54 versus
minimized library-backed R=56 (library L=124). The 32-bit candidate reached
complete local proofs but closed economically with
`DO_NOT_ADOPT_BITMAP_PATTERN`; broader validation and falsification were
not completed. No second supported bitmap pattern was adopted. Prefix_Sets
remains the established reusable pattern; generic proof content alone does
not guarantee cheap application integration.
See [bounded conclusion and coverage](tasks/019-bitmap-set-proof-pattern.md#observations-append-only-after-preregistration-commit).

```text
write implementation + authoritative contracts
              │
              ├── use reusable proof patterns where applicable
              │
              ▼
  spark-refine prove -P my_project.gpr   runs GNATprove (the proof authority),
              │                          then explains ONLY the result set that
              │                          run wrote (SRD001, SRD002); exit code =
              │                          GNATprove's
              │    (manual alternative: gnatprove -P ...; spark-refine explain)
              ▼
      understand the failure
              │
       fix appropriate layer  ──►  rerun GNATprove
```

For prover-robustness questions, run GNATprove once per prover and
compare the runs with `spark-refine compare-provers` (SRD003).

The public specification reads as domain behavior. Here is the fixed
pool from `examples/fixed_pool`:

```ada
procedure Allocate (P : in out Pool; Id : out Object_Id)
with Pre  => Free_Count (P) > 0,
     Post => Id_Sets.Contains (Free_Model (P)'Old, Id)
             and Free_Model (P) = Id_Sets.Remove (Free_Model (P)'Old, Id);
```

The private implementation stays optimized: a free-index stack and a
top index. In the library-backed variant, the application does not
hand-write the set model, the pigeonhole lemma or the loop invariants.
It instantiates `SPARK_Refine_Prefix_Sets`, states a short
representation invariant, and writes a one-call model adapter.

When a proof fails, `spark-refine explain` says what *kind* of failure it
is. Here is real output (abridged) for a seeded fault that pushes an
already-free identity on `Release`:

```text
SRD001: failed invariant may mask downstream postconditions
  severity: warning   confidence: high
  category: proof_context   action: fix_invariant_then_reprove
  entity:   Fixed_Pool.Release
  failed:
    fixed_pool.ads:50:14 VC_INVARIANT_CHECK [unproved]
  potentially affected:
    fixed_pool.ads:52:17 VC_POSTCONDITION [proved]
```

The `Release` postcondition is reported *proved*, but it rests on an
invariant that failed. A human or agent reading only "1 unproved check"
would miss that. The report also says what it does *not* know: no
postcondition is claimed to be false.

The tool should expose structure, not hide it, and it should never
pretend to be the prover.

## Three kinds of source

Both humans and agents work better when they know which layer they are
editing:

1. **Production implementation.** Normal engineering changes.
2. **Authoritative specification.** Public `Pre`/`Post`, abstract model
   semantics, user-owned requirements. High sensitivity. Do not weaken
   it merely to get a green proof.
3. **Mechanical proof support.** Representation invariants, model
   adapters, lemmas, loop invariants, proof-pattern instantiation. May be
   changed to make the proof architecture work. GNATprove still checks
   it.

This is a recommended policy, not something `spark-refine` enforces
today. See `docs/ARCHITECTURE.md` §3.

## Stable requirements, replaceable representations

A high-level model should be a component's semantic API for proofs.

```text
                   clients
                      |
                 contracts
                      |
                abstract model
               /      |       \
          repr A     repr B    repr C
```

Clients should not need to understand a container's private layout, and
neither should proof clients. The benchmarks confirmed this twice:

* moving the ring buffer from `First + Length` to `Head + Tail + Count`
  (Task 002) changed 0 lines of the public spec and the client proof;
* moving the fixed pool onto the library (Task 004) left the public API
  (visible part, CI-checked equivalent) and the client proof unchanged.

## A library of proof knowledge

The long-term asset is a set of **reviewed, versioned SPARK generics**.
Each one earns its place with evidence. Candidate families include
circular sequences, bounded vectors, free lists, bitmap sets, bounded
maps, state machines, ownership tables and descriptor rings.

Each pattern should ship with:

* its mathematical meaning;
* the supported representation family and its restrictions;
* independent validation instances proved by GNATprove;
* negative fixtures;
* per-instance burden (generic actuals and local SLOC) and proof-time
  effect;
* its trust assumptions, which should be none beyond SPARKlib;
* compatibility notes for SPARK/GNATprove versions.

Only one pattern exists today (`SPARK_Refine_Prefix_Sets`). Growth is
gated on benchmarks, not on a wish list. Note that the ring buffers'
19–21 SLOC of support did not by itself justify a library.

## What maturity could look like

### Level 1 — Reusable proof patterns

* reviewed SPARK generics;
* small, application-owned adapters and invariants;
* GNATprove verifies each instance.

Status: **demonstrated** for one pattern (fixed pool: 36 → 10 local
SLOC).

### Level 2 — Proof-aware diagnostics

* interpret SARIF / `.spark` / `.ali`;
* identify proof-engineering patterns such as invariant masking,
  client-only proof gaps and prover-portfolio dependency;
* give conservative semantic guidance, with explicit confidence and
  explicit "not evaluated" states.

Status: **implemented**:

* `spark-refine prove` (Task 008) runs GNATprove, then SRD001 and SRD002
  on the one result set **that run** wrote. This is orchestration only:
  it shows the exact command, preserves GNATprove's exit code, and
  proves nothing itself;
* `spark-refine explain` runs SRD001 and SRD002 on one existing result
  set, and does not run GNATprove;
* `spark-refine compare-provers` runs SRD003 over single-prover runs;
* all emit stable JSON.

### Level 3 — Semantic source enrichment

Possible future Libadalang work:

* identify the call and callee behind a failed precondition;
* identify the specific contract conjunct;
* map failures to source abstractions (model, invariant, adapter,
  library instance).

Status: **future**. Libadalang is not used today.

### Level 4 — Optional agentic proof engineering

AI agents consume structured diagnostics (`code`, `category`, `action`,
`confidence`) and choose the appropriate class of change, constrained by
policy and by GNATprove:

* authoritative requirements are not weakened silently;
* assumptions are not introduced silently;
* GNATprove performs the final check after every change;
* the developer reviews changes to authoritative specifications.

Status: **the interface exists** (`docs/AGENT_INTEGRATION.md`). Agent
tooling beyond that is future work.

### Where generation fits

Source generation is **not** a level of this ladder. It may come back as
a convenience technique if a future benchmark shows per-instance support
that a library cannot absorb. On current evidence it is deferred.

## Integration vision

* Alire for distributing proof-pattern libraries;
* GPR projects for build integration;
* GNATprove as the proof authority, and its SARIF / `.spark` output as
  the diagnostics input;
* SPARKlib functional containers as abstract models;
* Libadalang for semantic enrichment later;
* editor integration through existing Ada tooling (ALS, GNAT Studio,
  VS Code) consuming the JSON, not a custom IDE.

---

## Historical: the original generator-first vision

> **Status: historical.** The text below is the pre-Task 004 vision,
> kept unchanged except that its headings are demoted one level. Its
> `spark_refine validate` / `generate` / `diff` / `migrate` commands
> were never implemented and are not planned. Its maturity ladder, which
> put structural generation first, was replaced by the one above.

### One sentence

Make the abstraction layer of a SPARK proof a first-class, reusable engineering artifact rather than bespoke ghost-code plumbing recreated for every implementation.

### Developer experience we want

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

### Stable requirements, replaceable representations

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

### A community library of refinement knowledge

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

### Refactoring as a first-class proof operation

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

### Integration vision

The project should be a good citizen of the Ada/SPARK ecosystem:

- Alire for distribution;
- GPR projects for build integration;
- Libadalang for semantic inspection;
- SPARKlib functional containers for abstract models where appropriate;
- GNATprove as proof authority;
- `.spark`/SARIF ingestion for diagnostics;
- `Annotate` metadata for optional source-local declarations;
- editor integration through existing Ada tooling instead of a custom IDE.

### What maturity could look like

A mature release might support three levels of automation.

#### Level 1 — Structural generation

The user chooses a known pattern and the tool generates names, model mapping, predicates, and standard lemmas.

This is deterministic and should be the first production-quality level.

#### Level 2 — Proof-guided suggestions

The tool reads GNATprove output and proposes missing generated or user invariants based on the known refinement layer. Suggestions are explicit and reviewable.

#### Level 3 — Agentic proof engineering

An optional agent can iterate over failed proof obligations, but is constrained by policy:

- public requirements cannot be weakened silently;
- assumptions cannot be introduced silently;
- generated changes are categorized;
- GNATprove performs final checking;
- the developer receives a semantic diff.

The deterministic pattern system makes this far safer than unconstrained source editing.
