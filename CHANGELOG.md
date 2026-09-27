# Changelog

## Unreleased

### Added

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
  ground truth. It also adds 95 unit tests run in CI,
  `diagnostics/DIAGNOSTICS_METRICS.md` and
  `docs/tasks/005-proof-diagnostics-mvp.md`.

### Changed

- Root `alire.toml`: dropped the placeholder `maintainers` entry and the
  over-long `formal-verification` tag, which Alire 2.1.1 rejects. Without
  this change `alr build` fails at the repository root.
