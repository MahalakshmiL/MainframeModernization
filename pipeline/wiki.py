"""
wiki.py - Turns a rules.json (produced by pipeline/extract.py) into a
Confluence wiki-markup page: one table per program, every rule with
its citation and an SME confirm-or-correct status marker. No LLM
involved - this is pure formatting over already-cited rules.

Rules with no citation are dropped before they ever get here (that
check lives in extract.py's emit_rule tool), so nothing in this file
needs to re-validate citations - it only needs to render them.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from pipeline.parser import parse_all

CONFIRM_MACRO = "{status:colour=Yellow|title=NEEDS SME CONFIRM}"


def _group_by_program(rules):
    by_program = defaultdict(list)
    for r in rules:
        by_program[r.get("program", "UNKNOWN")].append(r)
    return by_program


def generate_wiki_page(rules, coverage=None, dead_paragraphs=None):
    coverage = coverage or {}
    dead_paragraphs = dead_paragraphs or {}
    by_program = _group_by_program(rules)

    lines = []
    lines.append("h1. Mainframe Knowledge Recovery — Business Rules (Draft)")
    lines.append("")
    lines.append(
        "{info:title=Review status}Every row below was extracted from a "
        "specific COBOL paragraph and carries its source citation. None of "
        "these are authoritative until an SME confirms or corrects "
        "them.{info}"
    )
    lines.append("")

    for program in sorted(by_program):
        prog_rules = by_program[program]
        lines.append(f"h2. {program}")
        lines.append("")

        cov = coverage.get(program)
        if cov:
            pct = cov.get("coverage_pct")
            if pct is None and cov.get("paragraphs_total"):
                pct = round(100 * cov["paragraphs_processed"] / cov["paragraphs_total"], 1)
            lines.append(
                f"*Coverage:* {cov.get('paragraphs_processed', '?')} / "
                f"{cov.get('paragraphs_total', '?')} reachable paragraphs "
                f"processed ({pct if pct is not None else '?'}%)"
            )
            lines.append("")

        lines.append("||Rule ID||Paragraph||Citation||Business Rule||Status||")
        for r in prog_rules:
            rule_id = r.get("rule_id", "-")
            paragraph = r.get("paragraph", "-")
            citation = r.get("citation", f"{r.get('source_file', 'src/' + program + '.cbl')}:{paragraph}")
            text = r.get("rule_text", "").replace("|", "\\|")
            lines.append(f"|{rule_id}|{paragraph}|{citation}|{text}|{CONFIRM_MACRO}|")
        lines.append("")

        dead = dead_paragraphs.get(program, [])
        if dead:
            lines.append(
                "{note:title=Excluded as dead code}The following paragraphs "
                "exist in source but are never PERFORMed from " + program +
                "'s entry point, so no rules were extracted from them: " +
                ", ".join(dead) + ".{note}"
            )
            lines.append("")

        lines.append("----")
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("usage: python -m pipeline.wiki output/rules.json [output/coverage.json]")
        sys.exit(1)

    rules = json.loads(Path(sys.argv[1]).read_text())
    coverage = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else {}

    programs = parse_all()
    dead_paragraphs = {name: data["dead"] for name, data in programs.items() if data["dead"]}

    page = generate_wiki_page(rules, coverage, dead_paragraphs)
    print(page)


if __name__ == "__main__":
    main()
