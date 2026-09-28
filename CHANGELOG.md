# Changelog

## Unreleased

### Added

- Task 009 (experimental, opt-in): Libadalang semantic enrichment of
  SRD002. `--semantic` for `explain`/`analyze`/`prove`, with `-P/--project`
  for `explain`/`analyze` and `-X NAME=VALUE` scenario values for the
  Libadalang project loader. Each SRD002 client failure gets a
  `resolution` (`exact`/`ambiguous`/`unresolved`/`unavailable`). An exact
  `VC_PRECONDITION` adds the call, the callee (qualified name,
  declaration), and the explicit `Pre` with top-level `and`/`and then`
  conjuncts. A `VC_ASSERT` adds the asserted expression only. The
  pre-registered experiment shows GNATprove 16.1.0 output is NOT
  ATTRIBUTABLE to a Pre conjunct, so `failed_conjunct` is always `null`.
  Source/result provenance gate: sources must match the result set's
  `.ali` `D` records (GNAT checksum, `gnat_checksum.py`, + second-resolution
  mtime). This is GNAT's source identity metadata, not byte identity:
  same-second layout/comment edits are undetectable. Reported as
  `analysis.semantic.provenance` (`layout_exact: false`, `byte_exact:
  false`). New modules
  `semantic.py` and `semantic_lal.py` (the only Libadalang import, lazy).
  `analysis.semantic` and `diagnostics[].semantic` are added only with
  `--semantic`, and `format_version` stays 1. Without the flag, output is
  byte-identical to Task 008. The core package still has no runtime
  dependencies. Libadalang is not on PyPI:
  `diagnostics/scripts/setup_libadalang.sh` builds a pinned, relocatable
  bundle (libadalang 26.0.0, 166 MB). Adds the new CI job
  `diagnostics-semantic` with E2E-F (project-local callees) and E2E-G
  (SPARKlib callees, fresh, same dependency checkout as the proof), 6
  semantic snapshot cases (432 KB), and 56 tests. The snapshots hold
  project-local source only. On an archived fixture, SPARKlib callee
  declarations may degrade to `unavailable` when the active checkout's
  mtime differs from the captured `D` record; the provenance gate is
  unchanged. SRD001–SRD003 are unchanged. There is no new rule.

- Task 008: `spark-refine prove -P PROJECT [-- GNATPROVE_ARGS...]`, fresh
  GNATprove orchestration (`diagnostics/spark_refine_diagnostics/orchestration.py`).
  It runs GNATprove as an argv (`shell=False`) after printing the exact
  command to stderr, and relays GNATprove's output to stderr so stdout
  carries only the report. It analyzes only the one result set whose
  `gnatprove.sarif` this run created or changed (stamp: dev, inode,
  size, mtime_ns, ctime_ns, sha256). Stale result sets are ignored;
  zero or several fresh result sets are refused. `--results PATH` must
  be freshly written, with no fallback. GNATprove's nonzero exit code is
  preserved even when diagnostics are produced; `--fail-on` applies only
  when GNATprove exited 0. Also adds `--gnatprove PATH` and `--dry-run`
  (with an optional JSON plan). `analysis.orchestration` is added to the
  JSON, and `format_version` stays 1. The real GNATprove 16.1.0
  repeated-run freshness behavior is recorded in
  `docs/tasks/008-proof-run-orchestration.md`. Adds 51 tests (fake
  GNATprove, no toolchain), fresh E2E-D/E-E in `diagnostics-e2e`, and
  installed-package `prove` checks. `explain`/`analyze`/`compare-provers`
  output on all 49 fixtures is byte-identical. SRD001–SRD003 are
  unchanged. There are no new rules and no runtime dependencies. The
  legacy Ada `spark_refine` now also redirects `prove`.

- Initial project motivation and ecosystem gap analysis.
- Architecture, trust model, MVP, benchmark, and roadmap documentation.
- Proposed manifest and circular-sequence proof pattern.
- Minimal Ada CLI bootstrap.
- Repository structural checks.
- Task 001: fully proved manual ring-buffer baseline (`examples/ring_buffer`)
  with a SPARKlib functional-sequence model, a representation-independent
  client proof, runtime tests, five machine-checked negative proof fixtures,
  a proof-support inventory (`BASELINE_METRICS.md`), and a pinned
  GNAT/GNATprove/SPARKlib 16.1.0 CI proof job.
- Task 004: reusable SPARK proof-pattern library `proof_patterns/`
  (`SPARK_Refine_Prefix_Sets`) with three independent proof-only validation
  instances; a library-backed fixed-pool variant
  (`examples/fixed_pool/variants/library_backed`) with an unchanged public
  API, client proof and runtime tests; public-API equivalence, inventory
  (`R`, `L`, `A`), negative (L1-L6) and library-validation gates; a new CI
  job; `LIBRARY_METRICS.md`. Pre-registered decision: PIVOT (R = 10).
- Task 005: deterministic GNATprove diagnostics MVP (`diagnostics/`,
  `python3 -m spark_refine_diagnostics`). It reads SARIF and `.spark`
  with the benchmark gates' classification (parity-tested), plus `.ali`
  through a narrow, non-raising GNAT 16.1.0 adapter. It has three stable
  rules:
  - SRD001: invariant masking risk;
  - SRD002: client-only proof gap; the public abstraction may be
    insufficient (medium confidence for preconditions, low for
    assertions; skipped when dependency information is unavailable);
  - SRD003: prover-portfolio dependency, only for checks matched
    `exact` or `unique_entity`, never by source order; ambiguous
    identities are reported as metadata.

  It ships 49 sanitized real GNATprove 16.1.0 fixtures, including a
  false-client-assertion control, with provenance and ablation-based
  ground truth. It also adds 110 fixture-based unit tests run in CI,
  a small fresh end-to-end GNATprove gate (one case per rule, CI job
  `diagnostics-e2e`), `diagnostics/DIAGNOSTICS_METRICS.md` and
  `docs/tasks/005-proof-diagnostics-mvp.md`. `.ali` files with a version
  header other than `GNAT Lib v16` are rejected (`unsupported_version`;
  SRD002 skipped).
- Task 006: the diagnostics are installable as the `spark-refine` console
  command (`python3 -m pip install ./diagnostics`; `pyproject.toml`,
  setuptools build-time only, no runtime dependencies; fixtures, tests
  and scripts are excluded from the wheel). It adds:
  - `spark-refine explain [PATH]`, the preferred name for single-run
    analysis. Without `PATH` it discovers exactly one GNATprove result
    set (`gnatprove.sarif` + `*.spark`) under the current directory.
    Zero or several candidates give exit 2, and several are listed in
    sorted order; the tool never guesses. `analyze` stays as a
    compatibility alias, and `python3 -m spark_refine_diagnostics` still
    works;
  - additive JSON fields (`format_version` stays 1): per-diagnostic and
    per-rule `category` / `action`, a derived top-level `summary`, and
    `analysis.input` for discovered result sets. `rules --format json`
    and `--version` are also new;
  - `docs/AGENT_INTEGRATION.md`, which documents the agent loop and the
    trust boundary;
  - `scripts/packaging_smoke.py` and CI job `diagnostics-packaging`,
    which build, inspect and install the wheel and run the installed
    CLI outside the repository.

  No new rule. SRD001–SRD003 behaviour is unchanged.

### Changed

- Task 006: the root README was rewritten around the evidence-backed
  project: reusable proof patterns plus proof-aware diagnostics. The
  original generator-centred README is preserved as
  `docs/history/ORIGINAL_README.md`. The root `alire.toml` description
  now reads "Reusable proof patterns and proof-aware diagnostics for
  SPARK". The Ada bootstrap `spark_refine` help now calls it legacy,
  points to the Python `spark-refine explain`, and marks
  `validate`/`generate`/`check` as historical, deprioritized research.

- Task 007: documentation realigned with the evidence-backed direction:
  reusable GNATprove-verified proof patterns plus proof-aware
  diagnostics, with GNATprove as the proof authority.
  - New [ADR 0005](docs/adr/0005-library-and-diagnostics-first.md),
    accepted. It prefers libraries and diagnostics over a
    generator-first architecture. ADRs 0003 and 0004 are marked
    superseded/deferred, and 0001 and 0002 are confirmed current.
  - `docs/VISION.md`, `ARCHITECTURE.md`, `MVP.md` and `ROADMAP.md` were
    rewritten around the current product. Each keeps its generator-era
    content in a labelled historical section.
  - `docs/SPEC.md` and `MANIFEST.md` got historical/deferred banners.
  - `LANDSCAPE.md`, `INTEGRATION.md`, `MOTIVATION.md`, `FAQ.md`,
    `METRICS.md`, `TRUST_MODEL.md`, `CONTRIBUTING.md` and `SECURITY.md`
    were updated.
  - Status notes were added to the remaining design documents.
  - The three kinds of source (implementation, authoritative
    specification, mechanical proof support) are documented as policy.
  - The human workflow is stated consistently:
    `gnatprove` → `spark-refine explain` (SRD001/SRD002; does not run
    GNATprove); SRD003 comes only from `compare-provers`.
  - README gains a "Where to start" documentation hierarchy.
  - `scripts/check_repo.py` now requires ADR 0005 and the Task 007
    record.

  Documentation-focused; no behavior change. See
  `docs/tasks/007-documentation-realignment.md`.

- Root `alire.toml`: dropped the placeholder `maintainers` entry and the
  over-long `formal-verification` tag, which Alire 2.1.1 rejects. Without
  this change `alr build` fails at the repository root.
