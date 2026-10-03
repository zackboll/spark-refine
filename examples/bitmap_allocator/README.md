# Task 019 packed bitmap benchmark and non-adopted research candidate

**Closed: `DO_NOT_ADOPT_BITMAP_PATTERN`.** Manual P=54; minimized
library-backed R=56; library L=124; A=6; reduction −3.703704%.
The 32-bit candidate reached complete local proofs but failed the frozen
economic criteria. Broader independent validation and complete falsification
were not completed; remaining campaigns stopped by post-measurement review.
Neither variant is presented as a production-ready supported container.

The manual benchmark is in `variants/manual/`; the unsupported research
candidate remains in `variants/library_backed/` at its measured paths.
See [closeout and coverage](../../docs/tasks/019-bitmap-set-proof-pattern.md#observations-append-only-after-preregistration-commit),
[manual metrics](BASELINE_METRICS.md), [historical library metrics](LIBRARY_METRICS.md),
[progress ledger](LIBRARY_EXPERIMENT_PROGRESS.md) and
[closeout evidence](../../docs/evidence/task019-bitmap-set-proof-pattern.json).
The intermediate metrics are preserved, not rewritten as adoption evidence.
Prefix_Sets remains the established reusable pattern; no second supported
bitmap pattern or release was adopted. Historical commands below are for
reproducibility, not instructions to resume optimization or validation.

Seventy identities (0 .. 69) occupy three `Interfaces.Unsigned_32` words.
One means free; zero means allocated. The last word has six valid bits and
26 zero padding bits. `Count` remains redundant production state.

The visible API describes a finite mathematical free set, not scan order.
The implementation scans valid identities low to high, clears the selected
bit and decrements Count; Release sets a bit and increments Count. No ghost
entity chooses a production word, mask, identity or Count value.

Local manual proof support operates on raw `Word_Array`, independently of
Pool validity. The Pool invariant ties Count to the raw model's length and
requires canonical padding. A non-adopted generic research artifact is retained
in `proof_patterns/src/`; broader configurations have not been validated.

From this directory:

```sh
alr -n build
./bin/bitmap_allocator_runtime_tests
alr -n build -- -XBITMAP_ASSERTIONS=on
./bin/assertions/bitmap_allocator_runtime_tests
python3 scripts/manual_evidence.py trust-scan
python3 scripts/manual_evidence.py positive
python3 scripts/proof_inventory.py
```

The positive checker runs GNATprove from a clean directory with the frozen
level-2 racing profile and invocation header; it inventories SARIF results
and cross-checks unproved VC identities against `.spark`. Artifacts are
ignored under `obj/measurements/`. `ablate` is measurement-only: it modifies
one proof artifact at a time, runs sequential clean proofs, and restores the
source in `finally`. Do not run concurrent builds/proofs during ablation.
Runtime tests use a test-local Boolean oracle, never as allocator storage.

Scope: fixed-size, nonvolatile, nonconcurrent allocator; ordinal mapping and
predefined integer identity equality. No atomic/hardware-register semantics.
See `BASELINE_METRICS.md` for the baseline status and evidence.

The canonical local cardinality is `Length (Bitmap_Model (Words))`, not a
second ghost bitmap or independently maintained ghost counter. This directly
supplies the allowed equivalent invariant `Count = Length (Bitmap_Model)`.
Raw model construction visits only valid IDs; real runtime membership uses
`Id / 32`, `Id mod 32` and `Shift_Left (1, ...)`. These expressions also cover
the preregistered first ID and 31/32, 63/64, 69 boundaries. No proof-only
mapping adapter, explicit mapping lemma or mutation helper was needed.