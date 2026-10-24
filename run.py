#!/usr/bin/env python3
"""
run.py - Orchestrates the full pipeline end to end.

    1. parser.py    - structural parse of src/*.cbl (deterministic)
    2. fields.py    - copybook field index, REDEFINES-aware (deterministic)
    3. extract.py   - Claude tool-use agent walks reachable paragraphs,
                       emits cited rules -> output/rules.json,
                       output/coverage.json  (needs ANTHROPIC_API_KEY)
    4. lineage.py   - field-level impact answers (deterministic)
    5. wiki.py      - Confluence-markup page from rules.json (deterministic)
    6. contradict.py - diffs rules.json against existing_pages/*.md and
                       cross-program COBOL comparisons (deterministic)
    7. report.py / dashboard.py - output/rules.csv, output/dashboard.html,
                       output/Rule-Recovery-Results.pdf (deterministic;
                       PDF step needs a local Chrome/Chromium/Edge install)
    8. score.py     - precision/recall/F1 + dead-code check vs ground_truth/
    9. open the generated pages (dashboard, chatbot, guide, wiki preview) in
                       your default browser - local files, so the chat
                       assistant on them won't respond (that only works
                       inside the real claude.ai viewer). Skip with --no-open.

Steps 1, 2, 4, 5, 6, 7, 9 never touch the network. Step 3 is the only one
that does, and this script stops before it (with instructions) if
ANTHROPIC_API_KEY isn't set, rather than silently skipping it.

Usage:
    python run.py                      # full pipeline, opens pages when done
    python run.py --skip-extract       # steps 1,2,4,5,6,7,9 only, reusing
                                        # an existing output/rules.json
    python run.py --no-open            # don't auto-open the browser
    python run.py --lineage-field ACCT-INT-RATE
"""

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"

from pipeline.env import load_dotenv
load_dotenv()


def step(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def run_deterministic_layer():
    from pipeline.parser import parse_all
    from pipeline.fields import build_field_index

    step("1-2. Deterministic parsing + field index")
    programs = parse_all()
    for name, data in programs.items():
        dead_note = f" ({len(data['dead'])} dead: {data['dead']})" if data["dead"] else ""
        print(f"  {name}: {len(data['paragraph_order'])} paragraphs, "
              f"{len(data['reachable'])} reachable{dead_note}")

    field_index = build_field_index()
    redefined = {k: v for k, v in field_index["equivalence"].items() if len(v) > 1}
    print(f"  {len(field_index['fields'])} fields indexed, "
          f"{len(redefined) // 2 if redefined else 0} REDEFINES pair(s) detected")
    return programs, field_index


def run_extract(args):
    step("3. Agentic extraction (Claude tool-use loop)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set - skipping extraction.")
        print("Set it and re-run without --skip-extract to actually call the model.")
        return False
    cmd = [sys.executable, "-m", "pipeline.extract"]
    if args.model:
        cmd += ["--model", args.model]
    if args.runs > 1:
        cmd += ["--runs", str(args.runs)]
    sys.stdout.flush()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


def run_lineage(field_index, field_name):
    from pipeline.lineage import answer_impact
    step(f"4. Field-level lineage: {field_name}")
    result = answer_impact(field_name, field_index)
    print(result.get("impact_summary", result.get("error")))
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "lineage_report.json").write_text(json.dumps(result, indent=2))
    print(f"  -> output/lineage_report.json")


def run_wiki_and_contradictions():
    from pipeline.wiki import generate_wiki_page
    from pipeline.contradict import find_contradictions
    from pipeline.parser import parse_all

    rules_path = OUTPUT_DIR / "rules.json"
    coverage_path = OUTPUT_DIR / "coverage.json"
    if not rules_path.exists():
        print("\nNo output/rules.json found - run extraction first "
              "(python -m pipeline.extract) or point at a rules file manually.")
        return

    rules = json.loads(rules_path.read_text())
    coverage = json.loads(coverage_path.read_text()) if coverage_path.exists() else {}

    step("5. Wiki page generation")
    programs = parse_all()
    dead_paragraphs = {name: data["dead"] for name, data in programs.items() if data["dead"]}
    page = generate_wiki_page(rules, coverage, dead_paragraphs)
    (OUTPUT_DIR / "wiki_page.confluence").write_text(page)
    print(f"  {len(rules)} rules rendered -> output/wiki_page.confluence")

    from pipeline.confluence_preview import write_preview
    preview_path = write_preview()
    print(f"  rendered preview -> output/{preview_path.name}")

    step("6. Contradiction detection vs existing_pages/ and cross-program drift")
    contradictions = find_contradictions(rules, programs)
    (OUTPUT_DIR / "contradictions.json").write_text(json.dumps(contradictions, indent=2))
    n = (len(contradictions["numeric_contradictions"])
         + len(contradictions["field_relationship_contradictions"])
         + len(contradictions["threshold_drift"]))
    print(f"  {n} contradiction(s)/drift(s) found -> output/contradictions.json")
    for c in contradictions["numeric_contradictions"]:
        print(f"    - [page vs code] [{c['page']}] says {c['page_numbers']}, code says "
              f"{c['code_numbers']} (matched {c['matched_rule_id']}, confidence {c['match_confidence']})")
    for c in contradictions["field_relationship_contradictions"]:
        print(f"    - [page vs code] [{c['page']}] {c['reason']}")
    for c in contradictions["threshold_drift"]:
        a, b = c["a"], c["b"]
        print(f"    - [cross-program drift, deterministic] {a['program']}:{a['paragraph']} "
              f"compares {c['field']} {a['operator']} {c['value']}, but "
              f"{b['program']}:{b['paragraph']} compares the same field/value with "
              f"'{b['operator']}' instead")


def run_reports():
    from pipeline.report import write_rules_csv, render_dashboard_pdf
    from pipeline.dashboard import write_dashboard
    from pipeline.chatbot import write_chatbot
    from pipeline.guide import write_guide

    rules_path = OUTPUT_DIR / "rules.json"
    if not rules_path.exists():
        return

    step("7. CSV + dashboard PDF + chatbot + guide export")
    rules = json.loads(rules_path.read_text())
    csv_path = write_rules_csv(rules)
    print(f"  {len(rules)} rules -> output/{csv_path.name}")

    html_path = write_dashboard()
    print(f"  dashboard -> output/{html_path.name}")

    chatbot_path = write_chatbot()
    print(f"  chatbot -> output/{chatbot_path.name}")

    guide_path = write_guide()
    print(f"  guide -> output/{guide_path.name}")

    pdf_path, error = render_dashboard_pdf(html_path)
    if pdf_path:
        print(f"  dashboard PDF -> output/{pdf_path.name}")
    else:
        print(f"  PDF skipped: {error}")


def run_score():
    rules_path = OUTPUT_DIR / "rules.json"
    coverage_path = OUTPUT_DIR / "coverage.json"
    if not rules_path.exists():
        return
    step("8. Scoring vs ground_truth/")
    cmd = [sys.executable, "score.py", "--rules", str(rules_path)]
    if coverage_path.exists():
        cmd += ["--coverage", str(coverage_path)]
    sys.stdout.flush()
    subprocess.run(cmd, cwd=PROJECT_ROOT)


PAGES_TO_OPEN = ["dashboard.html", "chatbot.html", "guide.html", "wiki_preview.html"]


def run_open_pages():
    existing = [OUTPUT_DIR / name for name in PAGES_TO_OPEN if (OUTPUT_DIR / name).exists()]
    if not existing:
        return
    step("9. Opening pages in your browser")
    for path in existing:
        webbrowser.open(path.resolve().as_uri())
        print(f"  opened output/{path.name}")
    print("  Note: the chat assistant on these local files won't respond - it only "
          "activates inside the real claude.ai viewer, not a plain browser tab.")


def main():
    argp = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argp.add_argument("--skip-extract", action="store_true",
                       help="Skip the LLM extraction step and reuse existing output/rules.json")
    argp.add_argument("--model", default=None)
    argp.add_argument("--runs", type=int, default=1)
    argp.add_argument("--lineage-field", default="ACCT-INT-RATE",
                       help="Field to run the impact answer for (default: ACCT-INT-RATE, "
                            "the REDEFINES field)")
    argp.add_argument("--no-open", action="store_true",
                       help="Don't automatically open the generated pages in your browser "
                            "when the run finishes")
    args = argp.parse_args()

    programs, field_index = run_deterministic_layer()
    run_lineage(field_index, args.lineage_field)

    if not args.skip_extract:
        ok = run_extract(args)
        if not ok and os.environ.get("ANTHROPIC_API_KEY"):
            print("Extraction failed - see error above.")
            sys.exit(1)

    run_wiki_and_contradictions()
    run_reports()
    run_score()

    if not args.no_open:
        run_open_pages()


if __name__ == "__main__":
    main()
