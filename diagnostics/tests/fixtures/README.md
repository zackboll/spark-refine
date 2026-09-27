# Diagnostics fixture corpus

49 fixtures of real GNATprove output. All of them were captured with the
pinned toolchain of Tasks 001–004: FSF GNATprove 16.1.0 (Why3 1.8.2,
CVC5 1.3.2, Z3 4.15.4, Alt-Ergo 2.6.1), using the projects' own Prove
switches (`--level=2 -U --mode=all --no-loop-unrolling …`). None is
hand-written.

* `manifest.toml`: provenance of each fixture (example, `obj/` directory,
  producer, edits, extra fixture-only sources).
* `<name>/fixture.json`: the same, written at capture time, plus a
  `provenance` block read from the raw output and the pinned `alire.toml`:
  * `benchmark`, `variant`, `case` (fault / ablation / extra client);
  * `gnatprove_version` (SARIF driver version), `gnat_version`,
    `sparklib_version`;
  * `ali_producer` (**GNAT 16.1.0**) and `ali_version_header`
    (`GNAT Lib v16`). The ALI adapter claims no compatibility with other
    compiler versions.
  * `prover_configuration` (the `--level=2` portfolio or a single
    `--prover=`), and the sanitized `command_line`;
  * `source_ref`: the commit whose benchmark sources were analysed.
* `../expectations.toml`: **hand-written** expected diagnostics and
  SRD001 ground-truth labels. The tests re-derive the labels from the
  ablation fixtures.

## Sanitization

Only content that no diagnostic reads is removed. Every check result is
kept.

| File | Kept | Dropped |
|---|---|---|
| `gnatprove.sarif` | version, tool name/version, invocation command line and exit code, **every result verbatim** (one per line) | `tool.driver.rules` (static rule catalogue), start/end timestamps |
| `<unit>.spark` | `stop_reason`, `pragma_assume`, entity names, per entry `rule/severity/file/line/col/entity/stats` | `check_tree`, `assumptions`, `timings`, `warn_error`, messages (duplicated in SARIF), … |
| `<unit>.ali` | `V`/`U`/`W`/`Z` lines | everything else |

The absolute checkout path in command lines is replaced by `<repo>`.

## Reproducing

Toolchain: `alr` with `examples/*/alire.toml` (as in CI).

```bash
# 1. benchmark-produced fixtures (producer = "benchmark")
cd examples/ring_buffer
python3 scripts/check_proof_results.py negative                        # N1, N2
python3 scripts/check_proof_results.py negative --variant head_tail_count  # B1-B6
python3 scripts/ablate_proof_support.py --only no_public_model_bound no_is_empty_post no_is_full_post
cd ../fixed_pool
python3 scripts/check_proof_results.py negative                        # P1-P6
python3 scripts/check_proof_results.py negative --variant library_backed   # L1-L6
python3 scripts/check_proof_results.py positive --variant library_backed
python3 scripts/ablate_proof_support.py --only spec_no_count_posts no_uniqueness_invariant \
    mask_p1_duplicate_initial mask_p4_release_wrong_id mask_p5_release_duplicate
python3 scripts/ablate_library_backed.py --only residual_no_invariant \
    mask_l1_duplicate_initial mask_l4_release_wrong_id mask_l5_release_duplicate
python3 scripts/prover_matrix.py
python3 scripts/prover_matrix.py --variant library_backed
cd ../..

# 2. fixtures produced through the benchmarks' run_case / gate code
python3 diagnostics/scripts/capture_fixtures.py produce

# 3. copy + sanitize into this directory
python3 diagnostics/scripts/capture_fixtures.py collect
python3 -m unittest discover -s diagnostics/tests -t diagnostics/tests
```

`produce` writes only to `examples/*/obj/` (git-ignored). It never
modifies committed sources.

## False client assertion (SRD002 control)

`pool_false_client_assert` is produced by `capture_fixtures.py produce`
(producer `case`) from two sources:

* the unchanged Task 003 `src/`;
* the fixture-only client unit in
  `../fixture_sources/fixed_pool_false_client/`.

Both are staged into `examples/fixed_pool/obj/srd_extra_src/…` and
analysed through the fixed-pool ablation `run_case`, so the switches and
toolchain are the benchmark's. The client calls `Initialize (P)` and then
asserts `Free_Count (P) = 0`, which is false because the proved
postcondition gives `Max_Objects`. Real result: `fixed_pool` has 108
checks, all proved; the client has 1 unproved `VC_ASSERT`.

## SRD003 ambiguity and reordering tests

No additional GNATprove fixture is needed for these:

* the reordering test shuffles the SARIF `results` (and `.spark` entries)
  of the committed prover-matrix fixtures in a temporary copy;
* the duplicate-identity and ambiguous-candidate cases are minimal
  synthetic runs. Real GNATprove 16.1.0 output never shows differing
  outcomes for one duplicate identity. Its only duplicate identity is a
  `VC_CONTAINER_AGGR_CHECK` reported 4× with identical outcomes.

The malformed-`.ali` and SARIF/`.spark`-disagreement cases are likewise
synthetic, made by damaging temporary copies of real fixtures.

## Ring buffer B ground truth

Removing B's invariant alone breaks `Push`'s postcondition even without a
fault (ablation `no_type_invariant`). That would make every Push fault
look "confirmed". The `ring_b*_mask` fixtures therefore apply the fault
together with the repository's control case
`control_push_ignores_tail_no_invariant`. In that case there is no
invariant, and `Push` computes its slot from `Head/Count` instead of
reading `Tail`. It proves 116/116 without a fault
(`ring_b_mask_baseline`). With this control:

* B3 and B4 expose their masked postconditions, as `REFACTOR_METRICS.md`
  reports.
* B1, B2 and B6 expose none.

For L5, the fixed-pool invariant-removal baseline already fails the
`Release` postcondition without any fault (`pool_l_mask_baseline`), so
the differential is not usable. L5's label rests on its byte-identical
edit to P5, which the differential does confirm (`basis = "equivalence"`,
checked by the tests).
