#!/usr/bin/env python3
"""Task 016 research-only structural inventory; never edits raw artifacts."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spark_refine_diagnostics.ali import load_ali_deps, read_ali
from spark_refine_diagnostics.loader import load_run, unit_from_entity
from spark_refine_diagnostics.spark_results import load_spark_dir
from spark_refine_diagnostics.sarif import parse_sarif


def investigate(directory):
    units = load_spark_dir(directory)
    run = load_run(directory)
    sarif = parse_sarif(directory / 'gnatprove.sarif')
    pool = defaultdict(list)
    for u in units:
        for e in u.entries:
            pool[e.key()].append(e)
    rows = []
    for i, c in enumerate(sarif.checks):
        key = (c.rule, c.location.file, c.location.line, c.location.column, c.entity)
        matches = pool[key]
        if matches:
            matches.pop(0)
            continue
        candidates = {}
        labels = ('rule', 'file', 'line', 'column', 'entity')
        all_entries = [e for u in units for e in u.entries]
        for j, label in enumerate(labels):
            candidates[label] = sorted({e.key() for e in all_entries
                                         if all(a == b for k, (a, b) in
                                                enumerate(zip(key, e.key())) if k != j)})
        path = sorted({e.key() for e in all_entries
                       if e.key()[0] == key[0] and e.key()[2:] == key[2:]
                       and Path(e.file).name == Path(key[1]).name})
        taxonomy = ('duplicate_cardinality_difference' if any(e.key() == key for e in all_entries)
                    else 'entity_identity_difference' if candidates['entity']
                    else 'location_difference' if candidates['line'] or candidates['column']
                    else 'rule_difference' if candidates['rule']
                    else 'path_normalization_difference' if path else 'unexplained')
        rows.append(dict(index=i, rule=c.rule, kind=c.sarif_kind, level=c.sarif_level,
                         suppressions=list(c.suppressions), file=c.location.file,
                         line=c.location.line, column=c.location.column, entity=c.entity,
                         status=c.status.value, fallback_unit=unit_from_entity(c.entity),
                         taxonomy=taxonomy, one_field_candidates=candidates,
                         path_candidates=path))
    spark = [dict(file=u.result.name+'.spark', unit=u.result.name,
                  stop_reason=u.result.stop_reason, proof=u.result.proof_entries,
                  flow=u.result.flow_entries) for u in units]
    ali = []
    for f in sorted(directory.glob('*.ali')):
        lines = f.read_text().splitlines()
        ali.append(dict(file=f.name, status=read_ali(f).status,
                        version=read_ali(f).version,
                        U=[line.split()[1] for line in lines if line.startswith('U ')],
                        W=[line.split()[1] for line in lines if line.startswith('W ')],
                        Z=[line.split()[1] for line in lines if line.startswith('Z ')]))
    spark_names = {u['unit'] for u in spark}
    ali_names = {r.split('%')[0].lower() for a in ali for r in a['U']}
    requested = set(run.unit_names())
    deps = load_ali_deps(directory, sorted(requested))
    authoritative = load_ali_deps(directory, sorted(spark_names))
    return dict(spark=spark, ali=ali, mismatches=rows,
                sets=dict(spark_units=sorted(spark_names), ali_units=sorted(ali_names),
                          fallback_only_units=sorted(requested-spark_names),
                          run_unit_names=sorted(requested), requested_ali_units=sorted(requested),
                          missing_requested_ali_units=sorted(requested-ali_names)),
                before=dict(issues=len(run.consistency_issues), disputed_units=sorted(run.disputed_units),
                            ali_status=deps.status, ali_problems=deps.problems),
                authority_probe=dict(status=authoritative.status, problems=authoritative.problems),
                counts={field: dict(sorted(Counter(row[field] for row in rows).items()))
                        for field in ('rule','kind','level','entity','taxonomy')})


if __name__ == '__main__':
    print(json.dumps(investigate(Path(sys.argv[1])), indent=2, sort_keys=True))