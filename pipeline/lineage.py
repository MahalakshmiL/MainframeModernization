"""
lineage.py - Field-level lineage and "what breaks if I change this"
answers. No LLM involved - this is the field index (fields.py) plus
the reachability graph (parser.py), formatted into prose.
"""

import json
import sys

from pipeline.fields import build_field_index


def _dedupe_sites(sites):
    seen = set()
    out = []
    for s in sites:
        key = (s["program"], s["paragraph"])
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def answer_impact(field_name, index=None):
    index = index or build_field_index()
    field_name = field_name.upper()

    if field_name not in index["fields"] and field_name not in index["equivalence"]:
        return {"field": field_name, "error": "field not found in any copybook"}

    equivalence_class = sorted(index["equivalence"].get(field_name, {field_name}))
    # Only fields that are actually elementary storage items get touch data.
    equivalence_class = [f for f in equivalence_class if f in index["fields"]] or [field_name]

    db2_mapping = {
        f: {"column": index["fields"][f]["db2_column"], "table": index["fields"][f]["db2_table"]}
        for f in equivalence_class if f in index["fields"]
    }

    live_readers, live_writers, dead_touches = [], [], []
    for f in equivalence_class:
        touches = index["touches"].get(f, {"reads": [], "writes": []})
        for site in touches["reads"]:
            entry = {**site, "field": f}
            (live_readers if site["reachable"] else dead_touches).append(entry)
        for site in touches["writes"]:
            entry = {**site, "field": f}
            (live_writers if site["reachable"] else dead_touches).append(entry)

    live_readers = _dedupe_sites(live_readers)
    live_writers = _dedupe_sites(live_writers)

    shares_storage = len(equivalence_class) > 1

    lines = []
    if shares_storage:
        others = [f for f in equivalence_class if f != field_name]
        lines.append(
            f"{field_name} physically shares storage (REDEFINES) with "
            f"{', '.join(others)}. They are the same bytes under different "
            f"names, so a write to one is a write to all of them - lineage "
            f"below covers the whole group."
        )
    if live_writers:
        writer_list = "; ".join(f"{w['program']}:{w['paragraph']}" for w in live_writers)
        lines.append(f"Written by: {writer_list}.")
    else:
        lines.append("Not written by any reachable paragraph in this fixture.")
    if live_readers:
        reader_list = "; ".join(f"{r['program']}:{r['paragraph']}" for r in live_readers)
        lines.append(f"Read by: {reader_list}.")
    if dead_touches:
        dead_list = "; ".join(f"{d['program']}:{d['paragraph']}" for d in dead_touches)
        lines.append(
            f"Also referenced in unreachable (dead) code, excluded from the "
            f"impact above: {dead_list}."
        )
    if db2_mapping:
        db2_list = "; ".join(
            f"{f} -> {m['table']}.{m['column']}" for f, m in db2_mapping.items() if m["table"]
        )
        if db2_list:
            lines.append(f"Lands in DB2 as: {db2_list}.")

    return {
        "field": field_name,
        "equivalence_class": equivalence_class,
        "shares_storage": shares_storage,
        "db2_mapping": db2_mapping,
        "live_writers": live_writers,
        "live_readers": live_readers,
        "dead_code_touches": dead_touches,
        "impact_summary": " ".join(lines),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m pipeline.lineage FIELD-NAME [FIELD-NAME ...]")
        sys.exit(1)

    index = build_field_index()
    results = {name: answer_impact(name, index) for name in sys.argv[1:]}
    for name, result in results.items():
        print(f"\n=== {name} ===")
        if "error" in result:
            print(result["error"])
            continue
        print(result["impact_summary"])

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
