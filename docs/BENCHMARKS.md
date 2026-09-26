# Benchmarks and Experiments

## Why benchmarks are part of the product design

Formal-methods tooling can easily move complexity rather than remove it. `spark-refine` needs evidence that it saves expert attention, not merely source lines.

Every stable pattern should have a benchmark that compares manual and generated proof engineering.

## Benchmark A — bounded circular buffer

### A1. Manual baseline

Implement and fully prove:

```text
representation: Content + First + Length
operations:     Push, Pop, Peek, Clear
model:          abstract sequence
```

Record all user-authored proof support.

**Status: done (Task 001).** See
[`examples/ring_buffer/BASELINE_METRICS.md`](../examples/ring_buffer/BASELINE_METRICS.md).
Measured with GNAT/GNATprove/SPARKlib FSF 16.1.0 at `--level=2`
(`--no-loop-unrolling`):

```text
production SLOC                     54
public specification SLOC           19   (developer-owned; not a generation target)
manual proof-support SLOC           19   model body 9, Refined_Post 5, loop invariants 5
  lemmas / repr. predicate / index helpers / refined op contracts / ghost updates: 0
checks (VCs + flow)                116   proved 116, unproved 0, justified 0
proof wall time                     ~2 s (-j0), nothing > 1 s, max 73 prover steps
negative fixtures                    5/5 detected at the expected (rule, entity)
```

The main finding is that the manual support is small and 100% generic. The
circular-index and wraparound reasoning needed **no** manual lemmas. The
hypothesis is assessed as *weaker*; see BASELINE_METRICS §10.

### A2. Generated refinement

Express the same public contract and implementation with the minimum pattern metadata necessary. Generate the refinement layer and prove again.

### A3. Representation refactor

Change concrete state to:

```text
Content + Head + Tail + Count
```

Keep the abstract contract unchanged.

**Status: done (Task 002).** See
[`examples/ring_buffer/REFACTOR_METRICS.md`](../examples/ring_buffer/REFACTOR_METRICS.md).
Same toolchain, switches, public spec (token-identical, CI-gated), client
proof and runtime tests (byte-identical, CI-gated):

```text
                                   A: First+Length   B: Head+Tail+Count
production SLOC                         54                 58
public specification SLOC               19                 19   (unchanged)
manual proof-support SLOC               19                 21
  representation invariant               0                  2   Type_Invariant: Tail = Physical_Index (Head, Count)
  lemmas / assertions / op. Refined_Post 0                  0
checks                                 116                134   (all proved, 0 justified)
proof wall time                        ~2 s               ~2-2.8 s
negative fixtures                      5/5 (N1-N5)        6/6 (B1-B6)
refactor churn: public API / contracts / client proof / tests = 0 lines
                proof support: 6 lines renamed, 2 lines new
```

Redundant state cost one invariant, needed only because `Push` writes
through `Tail`. `Tail` preservation across `Pop` and all wraparound
arithmetic proved automatically. The hypothesis is assessed as *weaker*
again. The recommendation is **more evidence** (Benchmark B, fixed pool),
with a pre-registered decision rule in REFACTOR_METRICS §12.

### A4. Client proof

Add a small client that proves a property through the abstract API, such as:

```text
Push(A); Push(B); Pop() returns A
```

Verify the client proof is unaffected by the representation refactor.

**Verified (Task 002):** the unchanged client proof proves against both
representations, and CI fails if it changes.

The client exists as of Task 001:
`examples/ring_buffer/proof/ring_buffer_client_proof.ad[sb]`
(`Push_Push_Pop` and `Rotate`). It exposed that `Is_Empty`/`Is_Full` need
model-level postconditions, and `Model` a public capacity bound, before any
client can discharge `Push`/`Pop` preconditions.

## Metrics

For each variant record:

```text
production LOC
public specification LOC
user-authored ghost/model LOC
user-authored lemma LOC
user-authored invariant LOC
generated LOC
number of GNATprove VCs
number of unproved VCs
proof wall time
peak memory if practical
number of files user modified during refactor
semantic requirement changes during refactor
```

Also record human-effort observations:

```text
Which obligation took the most reasoning?
Which generated artifact was hardest to understand?
What required pattern-specific manual code?
Did the tool report a useful error when the mapping was wrong?
```

## Negative fixtures

A proof generator needs adversarial tests.

Examples:

- off-by-one physical index mapping;
- length allowed to exceed capacity;
- append updates wrong slot;
- wraparound case omitted;
- `Pop` advances first before reading the old element;
- empty/full equivalence reversed;
- model function omits a storage element;
- generated helper accidentally uses an unchecked assumption.

The expected result must be failure at validation or GNATprove, not a green proof.

Task 001 implements five of these as machine-checked fixtures
(`examples/ring_buffer/negative/`): wrong append slot, wraparound
off-by-one, length exceeding capacity, wrong pop element, and a model that
reorders wrapped elements. The gate reads GNATprove's SARIF output and
requires each expected `(rule, entity)` obligation to be unproved; exit
codes and English message text are not used.

Task 002 adds six representation-B fixtures
(`examples/ring_buffer/variants/head_tail_count/negative/`): `Tail` not
advanced, `Tail` advanced twice, `Head` advanced wrongly in `Pop`, `Count`
not incremented, `Push` writing to `Head`, and `Clear` not resetting `Tail`.
Lesson: with a type invariant, a fault that breaks both the invariant and a
functional postcondition is reported **only** at the invariant. The
postcondition is discharged under the (failed, then assumed) invariant.
Fixtures must name the obligation that actually detects the fault.

## Benchmark B — fixed pool

This is the preferred second benchmark if circular sequence succeeds.

> **Task 002 outcome:** circular sequences turned out too easy to decide the
> generator question: 19–21 SLOC of support, no lemmas. This benchmark is
> now the deciding experiment. It should start with the free-index stack
> against `SPARK.Containers.Functional.Sets`, and must answer whether
> uniqueness/membership/cardinality refinement needs substantial *generic*
> lemmas. The GO/PIVOT thresholds are fixed in advance in
> `examples/ring_buffer/REFACTOR_METRICS.md` §12.

Representations:

```text
A: free-index stack
B: bitmap
```

Abstract model:

```text
Free_Set / Allocated_Set
```

The representation change is intentionally substantial and exercises a different mathematical abstraction.

## Stop criteria

The project should be willing to stop or pivot if the first two patterns show that:

- useful proof scaffolding cannot be generated without highly application-specific information;
- generated code is harder to debug than the manual proof it replaces;
- proof runtime grows unacceptably;
- representation refactors still require rewriting most user-owned proof code;
- source annotations/configuration become more verbose than the proof machinery they replace.

These are design results, not failures to be hidden.
