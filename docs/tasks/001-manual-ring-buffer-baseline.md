# Task 001 — Establish the Manual Circular-Buffer Proof Baseline

## Purpose

Before implementing `spark-refine`, establish the proof-engineering cost we are trying to remove. This task creates a complete, hand-authored SPARK proof for the first benchmark and records exactly which proof artifacts are necessary.

Do **not** write generator code in this task.

## Branch workflow

Create a feature branch:

```text
feature/001-ring-buffer-proof-baseline
```

Keep the branch focused on the baseline, tests, proof configuration, and measurements. Push the branch and open a pull request. Leave it unmerged for review.

## Starting point

The existing `examples/ring_buffer` source is a design fixture only. Its `Model` implementation is intentionally incomplete and must not be treated as verified code.

## Required implementation

Turn the fixture into a real bounded circular-buffer example with:

- fixed compile-time capacity;
- no dynamic allocation;
- `Content + First + Length` concrete representation;
- empty and full predicates;
- `Push` / append;
- `Pop` / remove first;
- `Peek`;
- `Clear` if it adds useful preservation evidence;
- an abstract ghost sequence model;
- SPARK contracts stated primarily in terms of the abstract model.

Prefer current SPARK functional-container facilities if they make the model clearer and are supported by the selected toolchain. If a simple ghost array is substantially easier for the baseline, document why and do not distort the implementation merely to fit the future generator.

## Proof objective

Run GNATprove at a meaningful proof level and reach a complete proof for the properties in scope, including run-time safety and all model/refinement contracts. Do not introduce `pragma Assume`, unchecked proof axioms, or intentionally unverified ghost functions to close obligations.

Record the exact GNATprove command, toolchain versions, prover configuration, timeout/steps, and final proof summary.

## Proof-support inventory

Every proof-only/support declaration should be classified in `examples/ring_buffer/BASELINE_METRICS.md` under one of:

```text
model construction
representation predicate
logical/physical index mapping
helper lemma
loop invariant
operation refinement contract
proof-only state update
other
```

For each category record:

- source LOC;
- number of declarations/assertions;
- short explanation of why they are required;
- whether the artifact appears generic to circular buffers or application-specific.

This inventory is the input to generator design. Do not optimize it away before recording it.

## Negative proof fixtures

Add at least the following intentionally broken variants or tests in a way that does not make normal CI red:

1. append writes to the wrong physical index;
2. wraparound calculation has an off-by-one error;
3. length can exceed capacity;
4. pop removes/returns the wrong logical element;
5. abstract model omits or reorders a wrapped element.

Document which GNATprove obligation fails for each. The future generator must preserve these failure modes rather than accidentally assuming them away.

## Client abstraction test

Add a small verified client using only the public abstract API. It should establish a property equivalent to:

```text
Push(A)
Push(B)
Pop -> A
remaining Model = [B]
```

The client must not depend on `First`, `Length`, physical indices, or `Content`.

This client will later be reused unchanged during the representation-refactor benchmark.

## Documentation updates

Update:

- `docs/BENCHMARKS.md` with actual baseline numbers;
- `docs/PROOF_PATTERNS.md` with proof facts that turned out to be genuinely necessary;
- `docs/MVP.md` if the experiment exposes incorrect assumptions;
- `examples/ring_buffer/README.md` with build/prove instructions;
- new `examples/ring_buffer/BASELINE_METRICS.md` with detailed measurements.

Do not change the project mission to fit the benchmark. If the experiment suggests refinement automation is less valuable than expected, document that explicitly.

## CI

Add an Ada/SPARK CI job only after it can run reliably. It should:

- install/pin the selected Ada/SPARK toolchain;
- build the example;
- execute any runtime tests;
- run GNATprove;
- fail if expected proof obligations are not discharged;
- run the existing repository checks.

Do not claim CI proof coverage that the workflow does not actually enforce.

## Acceptance criteria

The task is complete when all of the following are true:

- the manual ring buffer is implemented rather than a placeholder;
- the public behavior is expressed using an abstract model;
- the in-scope example has no unproved VCs;
- no prohibited assumptions were introduced;
- negative fixtures demonstrate that meaningful implementation/model defects are detected;
- a representation-independent client proof passes;
- proof-support code is categorized and measured;
- exact commands/toolchain versions are documented;
- local validation and CI (if configured) agree;
- branch is pushed and a pull request is open and unmerged.

## Final report for review

The PR/task report should include:

1. starting SHA and final SHA;
2. toolchain versions;
3. exact build/test/GNATprove commands;
4. final proof result and VC counts;
5. manual proof-support LOC by category;
6. the three most difficult proof obligations and why;
7. results of each negative fixture;
8. whether the original `spark-refine` hypothesis looks stronger, weaker, or unchanged based on measured evidence;
9. concrete candidates for what Task 002 should generate;
10. confirmation that the PR is open, unmerged, and the branch/PR/local heads match.
