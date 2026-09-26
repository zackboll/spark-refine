# Fixed object pool — manual proof baseline (Task 003)

This benchmark is a fixed-capacity object allocator (`Max_Objects = 32`)
implemented as a free-index stack. It is proved in SPARK against one
authoritative mathematical model:

```text
Free_Model (P) : SPARK.Containers.Functional.Sets.Set of Object_Id
Is_Allocated (P, Id)  <=>  not Contains (Free_Model (P), Id)
```

It is a **manual** proof experiment. Nothing here is generated.

| Path | Contents |
|---|---|
| `src/fixed_pool.ads` | public spec (authoritative contracts) + private representation + uniqueness `Type_Invariant` |
| `src/fixed_pool.adb` | production bodies, derived ghost `Free_Model`, `Lemma_Universe_Bound` |
| `proof/` | representation-independent client proof (public API only; no LIFO assumption) |
| `tests/` | executable runtime tests (public API only) |
| `negative/P*/fault.toml` | single-fault fixtures P1–P6 with expected `(rule, entity)` |
| `proof_inventory.toml` | line-exact classification: production / specification / mechanical |
| `scripts/check_proof_results.py` | trust scan, positive gate, negative gate (SARIF + `.spark`) |
| `scripts/proof_inventory.py` | SLOC, `P`, generic fraction `G` (fails on drift) |
| `scripts/ablate_proof_support.py` | ablation + invariant-masking study (measurement) |
| `scripts/prover_matrix.py` | CVC5-only / Z3-only / Alt-Ergo-only runs (measurement) |
| `BASELINE_METRICS.md` | all results and the pre-registered decision |

```bash
cd examples/fixed_pool
alr -n build && ./bin/fixed_pool_runtime_tests
alr -n build -- -XFIXED_POOL_ASSERTIONS=on && ./bin/assertions/fixed_pool_runtime_tests
python3 scripts/proof_inventory.py
python3 scripts/check_proof_results.py all    # trust-scan, positive, negative
```

Toolchain pins and proof switches are identical to `examples/ring_buffer`
(gnat_native, gnatprove and sparklib 16.1.0; gprbuild 26.0.1;
`--level=2 --no-loop-unrolling`).

Result: 136/136 checks proved, `P = 36`, `G = 100 %`, `M = 5`. The
pre-registered decision is **REVIEW** (see `BASELINE_METRICS.md` §13).
