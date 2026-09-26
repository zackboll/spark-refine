# Ring-buffer manual proof baseline (Benchmark A1)

A bounded FIFO queue (`Max_Size = 16`) implemented with a fixed array plus
`First` and `Length`, **fully proved by hand** with GNATprove against a
public abstract model: a SPARKlib functional sequence
(`SPARK.Containers.Functional.Vectors`). This is the Task 001 baseline
against which `spark-refine` generation will be measured. No generator code
is involved.

Results, measurements, difficulty analysis and the hypothesis assessment are
in [`BASELINE_METRICS.md`](BASELINE_METRICS.md). In short: **116/116 checks
proved, 0 unproved, 0 justified, ≈ 2 s**. The hand-written proof support is
19 SLOC (model body, `Refined_Post`, 2 loop invariants), all of it generic,
with no lemmas and no representation predicate.

## Layout

```text
alire.toml                 pinned toolchain: gnat_native/gnatprove/sparklib 16.1.0
ring_buffer.gpr            build + proof configuration (package Prove)
spark-refine.toml          future generator manifest (design; unused here)
proof_inventory.toml       machine-readable classification of every source line
src/ring_buffer.ads/.adb   implementation, public spec, manual proof support
proof/                     representation-independent client proof (A4)
tests/                     executable runtime tests (public API only)
negative/<fixture>/        five deliberately broken variants (fault.toml)
scripts/                   proof gate, inventory and ablation tools
generated/                 reserved for future generator output (empty)
```

## Public API

| Operation | Contract (abstract) |
|---|---|
| `Model (B)` (ghost) | `Last (Model (B)) <= Max_Size` |
| `Is_Empty (B)` / `Is_Full (B)` | `= (Last (Model (B)) = 0)` / `= (Last (Model (B)) = Max_Size)` |
| `Initialize (B)` / `Clear (B)` | `Model (B) = Empty_Sequence` |
| `Push (B, E)` | `Pre not Is_Full`; `Model (B) = Add (Model (B)'Old, E)` |
| `Pop (B, E)` | `Pre not Is_Empty`; `E = Get (Model'Old, 1)` and `Model = Remove (Model'Old, 1)` |
| `Peek (B, E)` | `Pre not Is_Empty`; `E = Get (Model, 1)`; `B` is `in` |

## Build, test and prove

Requires Alire 2.1.1. From this directory:

```bash
alr -n update                                   # fetches the pinned toolchain
alr -n build                                    # production build
./bin/ring_buffer_runtime_tests                 # runtime tests

alr -n build -- -XRING_BUFFER_ASSERTIONS=on     # same tests with every contract
./bin/assertions/ring_buffer_runtime_tests      #   and the ghost model executed

python3 scripts/check_proof_results.py all      # trust scan + positive proof + negative fixtures
python3 scripts/proof_inventory.py              # proof-support measurements
python3 scripts/ablate_proof_support.py         # necessity of each proof artifact
```

A bare interactive proof is `alr -n exec -- gnatprove -P ring_buffer.gpr -j0`;
the switches live in `ring_buffer.gpr`. Build and proof artifacts go to
`obj/` and `bin/` (both ignored); nothing is written into `src/`.

## Client proof

`proof/ring_buffer_client_proof.ad[sb]` uses only the visible abstraction
(`Model`, `Sequences`, public operations):

* `Push_Push_Pop`: `Initialize; Push (A); Push (B); Pop (X)` ⇒ `X = A` and
  `Model (Q) = [B]`;
* `Rotate`: on any non-empty queue, `Peek; Pop; Push` moves the head to the
  tail.

It is meant to be reused **unchanged** by the representation-refactor
benchmark (A3).

## Negative fixtures

`negative/*/fault.toml` holds one targeted fault each: wrong append slot,
wraparound off-by-one, capacity overflow, wrong pop and wrong model order.
The gate applies each patch to a scratch copy of `src/` and requires specific
`(rule, entity)` obligations to be **unproved** in GNATprove's SARIF output.
See `BASELINE_METRICS.md` §8.
