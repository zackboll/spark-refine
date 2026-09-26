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

### A2. Generated refinement

Express the same public contract and implementation with the minimum pattern metadata necessary. Generate the refinement layer and prove again.

### A3. Representation refactor

Change concrete state to:

```text
Content + Head + Tail + Count
```

Keep the abstract contract unchanged.

### A4. Client proof

Add a small client that proves a property through the abstract API, such as:

```text
Push(A); Push(B); Pop() returns A
```

Verify the client proof is unaffected by the representation refactor.

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

## Benchmark B — fixed pool

This is the preferred second benchmark if circular sequence succeeds.

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
