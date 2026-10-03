# Task 021 replay artifacts

Observed historical maintenance trial, not a new product feature, upstream
contribution, cryptographic certification or current vulnerability finding.
See [session report](../../tasks/021-proof-workflow-pilot.md). The patch excerpt
is from Ada_CRDT, copyright (c) 2026 bladeacer, MIT; the accompanying
`UPSTREAM-LICENSE.txt` preserves its notice. The driver is separate trial code.
No upstream implementation is vendored.

## Replay manually, outside normal CI

Use Alire 2.1.1, GNAT/GNATprove **FSF 16.1.0**, the publishing manifest and
root `crdt.gpr` at the exact base below, not later upstream code. Install the
spark-refine diagnostics CLI from product revision
`713bd41e9601587fd54d7324a57aef3268b8105f` in a dedicated venv. Verify its
`spark_refine_diagnostics.__file__` before proving. No Libadalang required.
Commands assume the artifact directory is this reviewed report's directory.

```sh
PRODUCT=/home/zboll/git/spark-refine
ARTIFACTS="$PRODUCT/docs/examples/task021"
TRIAL="$PRODUCT/diagnostics/obj/task021-replay"
mkdir -p "$TRIAL"
git clone --no-checkout https://github.com/bladeacer/Ada_CRDT.git "$TRIAL/working"
git -C "$TRIAL/working" checkout --detach 5fa2c0cee62deb86368fcc84a8d3b06726028276
git -C "$TRIAL/working" archive HEAD > "$TRIAL/starting-tree.tar"
git -C "$PRODUCT" diff --exit-code 713bd41e9601587fd54d7324a57aef3268b8105f -- \
  diagnostics/spark_refine_diagnostics diagnostics/pyproject.toml
python3 -m venv "$TRIAL/venv"
"$TRIAL/venv/bin/python" -m pip install -e "$PRODUCT/diagnostics"
"$TRIAL/venv/bin/python" -c 'import spark_refine_diagnostics as s; print(s.__file__)'
export PATH="$TRIAL/venv/bin:$PATH"
cd "$TRIAL/working"
alr -n build --stop-after=generation
alr exec -- gnatprove --version
# New, unused subdir for EVERY proof: never reuse historical artifacts.
alr exec -- spark-refine prove -P crdt.gpr --show-unproved --format json \
  -- -j 30 --steps 10000 --no-loop-unrolling \
  --subdirs=task021-replay-before --output-header \
  > "$TRIAL/before.json" 2> "$TRIAL/before.log"
git apply --check "$ARTIFACTS/sha256-update.patch"
git apply "$ARTIFACTS/sha256-update.patch"
git diff --check
alr exec -- spark-refine prove -P crdt.gpr --show-unproved --format json \
  -- -j 30 --steps 10000 --no-loop-unrolling \
  --subdirs=task021-replay-after --output-header \
  > "$TRIAL/after.json" 2> "$TRIAL/after.log"
```

Inspect `analysis.orchestration.result_path` and header: discovery observes
the actual location. In this session it was `obj/SUBDIR/gnatprove`; subsequent
runs selected that confirmed location explicitly with `--results`. Do not
guess on another project. Both commands' exit 0 can coexist with failures.
Inspect `analysis.unproved_checks`, `notes`, `analysis.rules` and the existing
loader's `load_run(Path(actual_result_path))` for scope and disputed checks.
`observations.json` is a compact excerpt, not substitute raw artifacts; local
artifact inventory hashes include this session's absolute paths.

For success acceptance, run the unchanged patched candidate twice more,
sequentially, with unused `task021-replay-confirm1` and `task021-replay-confirm2`
subdirectories and otherwise identical commands/settings. Preserve logs and
check coverage and disputes, not only counts. Never run two proofs concurrently.

## Independent runtime check

```sh
mkdir -p "$TRIAL/runtime"
cp "$ARTIFACTS/runtime.gpr" "$ARTIFACTS/sha256_driver.adb" "$TRIAL/runtime/"
alr exec -- gprbuild -P "$TRIAL/runtime/runtime.gpr" \
  -XUPSTREAM="$TRIAL/working" --subdirs=normal -p
python3 "$ARTIFACTS/check_runtime.py" "$TRIAL/runtime/bin/normal/sha256_driver"
alr exec -- gprbuild -P "$TRIAL/runtime/runtime.gpr" \
  -XUPSTREAM="$TRIAL/working" --subdirs=assertions -p -cargs:Ada -gnata
python3 "$ARTIFACTS/check_runtime.py" "$TRIAL/runtime/bin/assertions/sha256_driver"
alr exec -- gprbuild -P crdt.gpr --subdirs=task021-upstream-runtime -p
./task021-upstream-runtime/test_crdt
```

`runtime_cases.json` records exact hex bytes, signed 64-bit array origins,
chunk lists and independent hashlib digests. Patterned messages use
`byte[i] = (37*i + 11) mod 256`, for zero-based `i`. Whole/one-byte/irregular
chunkings include 13 then 52 then remainder (crosses 64 when available), plus
intervening zeros. Every zero chunk calls Update on both an extreme legal null
array and a legal `1 .. 0` slice; empty messages also use extreme null bounds.
The test driver prints one-shot and streaming hashes; the Python checker
verifies both against hashlib, recomputing every saved oracle.

Normal driver build compiles its four-unit dependency closure without
`-gnata`; assertions build recompiles the same four units with `-gnata`:
driver, CRDT, CRDT.Security and CRDT.Security.SHA256. Upstream root build uses
its unchanged `-gnata` configuration for its compiled units. Runtime drivers
are not included in the unchanged whole-project proof scope. No enormous
arrays, heap additions in production, or swallowed exceptions.