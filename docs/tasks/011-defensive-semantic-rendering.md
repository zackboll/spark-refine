# Task 011 — Make semantic rendering fail-safe

Status: implemented. Base: `origin/main`
`e231965c59bb0a70a34c40743fb63c6e7f1d6a31` (contains the reviewed Task 010
head `a07698e7`). Maintenance task: presentation hardening only.

## Result in one paragraph

Text rendering of Task 009 semantic enrichment no longer raises on a
malformed or incomplete internal semantic object. An `exact` entry is
rendered in full only if it satisfies the same structural contract Task 010
grouping uses. The contract lives in a new backend-neutral module,
`semantic_shape.py`. Anything else renders as `semantic entry: incomplete`
with a fixed reason, and none of its call/callee/Pre/conjunct/assertion
facts appear. JSON is unchanged: the raw semantic object is still
serialised verbatim. For every valid report, the text output is
byte-identical to `origin/main`. SRD001–SRD003, semantic resolution,
Libadalang, provenance, grouping and the failed-conjunct policy are
unchanged.

## 1. The gap (found by Task 010)

`render.semantic_text()` assumed that every `resolution == "exact"` entry
was structurally complete:

* it picked the precondition or assertion branch by **`"call" in c`**, not
  by rule, and then indexed `c["precondition"]`, `c["call"]["text"]`,
  `c["callee"]["declaration"]`, `pre["conjuncts"]`, `a["location"]`, ... ;
* the header indexed `sem["backend"]`, `sem["checks"]` and
  `c["location"]["file"]`.

`{"resolution": "exact", "call": {}}` therefore raised `KeyError` in the
full report. On `origin/main`, the new adversarial tests fail with
`KeyError`, `TypeError` and `AttributeError`. Task 010 had already treated
such entries as `semantic_incomplete` for grouping. Only the per-diagnostic
renderer read the raw object.

These objects are internal. The Libadalang backend (`semantic_lal.py`) and
`semantic.py` do not produce them today. The hardening makes the optional
enrichment non-fatal all the way through presentation, as it already was
through resolution and grouping.

## 2. Design

```text
semantic_shape.py (NEW)   exact_precondition_complete(c)
                          exact_assertion_complete(c)
                          span_ok, is_int, nonempty_str, ATTRIBUTION
   ↑                    ↑
semantic_groups.py      render.py
(Task 010: incomplete   (Task 011: incomplete -> "semantic entry:
 -> semantic_incomplete)  incomplete", no facts rendered)
```

**Shared structural validation (decision).** Task 010's private
`_complete()` was already a pure structural predicate over the exact Task
009 shape. It had no grouping policy in it. It moved **verbatim** into
`semantic_shape.exact_precondition_complete()`, and `semantic_groups.py`
imports it (`_complete` stays as an alias). The renderer uses the same
predicate, so "complete enough to group" and "complete enough to render"
are one definition. `SharedContract.test_grouping_and_rendering_agree`
checks this on every corruption. `render.py` imports `semantic_shape` only.
It never imports `semantic_groups` (grouping policy or construction),
`semantic`, `semantic_lal` or Libadalang, and this is AST-checked.
`semantic_shape.py` imports nothing.

This choice is deliberately strict. The renderer does not print a partial
entry such as "call known, callee missing". An exact precondition entry is
either the full Task 009 structure (including `failed_conjunct: null` and
`attribution: "not_provided_by_gnatprove"`, which is what justifies the
rendered "failed conjunct: unknown" line) or it is incomplete. This also
avoids a second, looser definition of completeness.

**New assertion contract.** `exact_assertion_complete()`: `assertion` is a
dict with string `pragma`, string `text` and a complete `location` span.
`enclosing_subprogram` is absent, `None` or a non-empty string. This is
exactly what `semantic_lal.resolve_assertion()` emits. Grouping never
needed it (an assertion is always `assertion_has_no_callee`).

**Dispatch by rule.** Exact entries are dispatched on `rule`, the same way
`semantic.py` dispatches to the backend: `VC_PRECONDITION` → call context,
anything else → assertion context. The renderer no longer looks at which
keys happen to be present. A `VC_ASSERT` entry that carries call/callee/Pre
keys is therefore judged only by the assertion contract, and none of those
keys are rendered.

**Envelope.** A non-dict semantic block, non-list `checks` or non-dict
check renders a `semantic entry: incomplete` line with a structural
reason. A missing `backend`, `location` part, `rule` or `resolution`
renders as `-`. `semantic_meta_text()` uses `.get` in the same way. Every
value that is present renders exactly as before.

**No exception swallowing.** No `try` block was added. Robustness comes
from explicit structural checks, and `render.py` contains no `try` at all
(AST-checked).

Rendered forms:

```text
    ring_buffer_client_proof.adb:10:7 VC_PRECONDITION: exact
      semantic entry: incomplete
      reason: exact semantic entry lacks complete call/callee/Pre data

    ring_buffer_client_proof.adb:16:43 VC_ASSERT: exact
      semantic entry: incomplete
      reason: exact semantic entry lacks complete assertion data
```

## 3. Malformed structures now handled

Every case goes through `to_text` (full report, including the real Task 010
triage section), `diagnostic_to_text` and `semantic_text`. Each case checks
four things: rendering does not raise, the output says `semantic entry:
incomplete`, no `call:` / `callee:` / `public Pre:` / `failed conjunct:` /
`[i]` / `assertion:` / `in:` line appears, and none of the entry's fact
strings (call text, callee name, Pre text, declaration file, assertion
text, enclosing subprogram) appears anywhere in the report.

* **Precondition**: missing call, `call = {}`, call not a dict,
  `call.text` missing, `call.location` missing; callee missing / `{}` /
  not a dict, `callee.name` missing / not a string, `declaration` missing /
  `{}`; precondition missing / `None` / `{}`, `explicit` missing, `text`
  missing, `conjuncts` missing / not a list, a conjunct `None`,
  `attribution` missing. In addition, all of Task 010's `MALFORMED_EXACT`
  and `MALFORMED_IMPLICIT` corruptions (wrong types, empty strings, `bool`
  as `int`, partial spans, claimed `failed_conjunct`, other attribution,
  explicit=False with text/location, ...).
* **Assertion**: assertion missing / `{}` / not a dict / `None`,
  `assertion.text` missing / not a string, `assertion.location` missing /
  `None` / `{}` / partial, `assertion.pragma` missing,
  `enclosing_subprogram` not a string / empty. Also: a `VC_ASSERT` carrying
  precondition keys.
* **Envelope**: semantic a list / string, `checks` missing / `None` /
  dict, `backend` missing, check not a dict, empty check, `location`
  missing / `None` / partial, `resolution` missing, `rule` missing on an
  exact `{"call": {}}`. Grouping is out of scope here: `semantic.py` builds
  this envelope itself, and Task 010 is unchanged.
* **Motivating case**: `{"resolution": "exact", "call": {}}`, both alone
  and beside a valid sibling in the full report. The sibling still renders
  its call, callee and Pre once. The broken entry renders as incomplete.
  Grouping still gives 1 group plus 1 `semantic_incomplete`.

Controls that stay complete: single conjunct, several conjuncts, empty
conjunct list, no explicit Pre, and an assertion with `enclosing_subprogram`
`None` or absent.

## 4. Compatibility evidence

* **Valid text, byte-for-byte.** A harness rendered one fixed corpus with
  both `origin/main` (git worktree) and this branch, then compared the
  outputs with `cmp`. The corpus contained:
  * every committed fixture without semantic enrichment (text + JSON);
  * every semantic snapshot enriched by a stub answering complete Task 009
    entries in four variants (single conjunct, multi-line multi-conjunct,
    implicit Pre with assertion without enclosing subprogram, mixed
    exact/ambiguous);
  * every snapshot with `--semantic` but no project (not evaluated);
  * the semantic metadata, triage section and per-diagnostic semantic
    blocks of the real fresh E2E-F and E2E-G reports from the `main` CI run
    36506194791;
  * every semantic snapshot enriched by **real Libadalang 26.0.0** under
    `alr exec` (text + JSON).

  Result: 178 outputs, **byte-identical**. None of them contains `semantic
  entry: incomplete`. The golden-line tests in `ValidRenderingIsUnchanged`
  pin the valid forms in the suite.
* **JSON.** `diagnostic_to_dict()` is unchanged. The tests check that every
  malformed semantic object, including a non-dict one, is serialised
  verbatim and that rendering does not mutate it. `format_version` stays 1.
* **Task 010 groups.** The grouping logic is unchanged: the same predicate
  moved modules, and no reason was added. Headline evidence on real
  Libadalang: `ring_no_is_full_post` → 1 Push group (3 checks);
  `pool_false_client_assert` → 0 groups. The E2E-G CI report (fresh,
  SPARKlib) → 4 groups (`Pop`, `Push`, `Sequences.Get`,
  `Sequences.Remove`), and `coverage_problems` is `[]`.

### Behaviour change, stated

Before this task, an exact entry that was not structurally complete either
raised or, when it happened to be indexable (for example an explicit Pre
without a `location` span, as the Task 009 test `FakeBackend` produces),
rendered its facts even though Task 010 already called it
`semantic_incomplete`. It now renders as `semantic entry: incomplete`, which
matches the triage section. No valid Task 009 entry is affected.

## 5. Unchanged

SRD001, SRD002, SRD003, the diagnostic count and confidence,
`semantic.py`, `semantic_lal.py`, the provenance gate, the resolution
vocabulary, the failed-conjunct policy (always `null`), grouping, the
`ungrouped` reason vocabulary, JSON, the CLI, proof behaviour and the seven
CI jobs. There is no new E2E case. `setup_libadalang.sh` is unchanged, so
the Libadalang CI cache key is unchanged.

## 6. Tests

New `diagnostics/tests/test_semantic_render.py` (21 tests, no Libadalang;
it reuses the Task 010 builders and corruption lists). On `origin/main`
these tests fail with `KeyError` / `TypeError` / `AttributeError`.
`packaging_smoke.py` also requires `semantic_shape.py` in the wheel, and
`scripts/check_repo.py` requires the new module and this document.
