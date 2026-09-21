#!/usr/bin/env python3
"""
score.py - Scores a submitted rule-extraction output against the
SME-validated ground truth for the mainframe knowledge recovery
fixture.

Usage:
    python score.py --rules output/rules.json [--coverage output/coverage.json]

Expected submission format for --rules (a JSON list):
    [
      {
        "program": "DEPOSIT",
        "paragraph": "3100-CHECK-FEE-WAIVER",
        "rule_text": "If the resulting balance is $500 or more, the fee is waived.",
        "citation": "src/DEPOSIT.cbl:3100-CHECK-FEE-WAIVER"
      },
      ...
    ]

Expected submission format for --coverage (a JSON object, optional):
    {
      "DEPOSIT": {"paragraphs_total": 6, "paragraphs_processed": 6},
      "INTCALC": {"paragraphs_total": 8, "paragraphs_processed": 7}
    }
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

GROUND_TRUTH_DIR = Path(__file__).parent / "ground_truth"

# Paragraphs in ACCTMSTR that exist in source but are never PERFORMed.
# Any submitted rule citing one of these as live business logic is a
# false positive that the scoring must catch.
DEAD_PARAGRAPHS = {
    "ACCTMSTR": {"4700-LEGACY-OVERDRAFT-CHARGE", "4750-LEGACY-OVERDRAFT-NOTIFY"},
}

TEXT_MATCH_THRESHOLD = 0.35


def load_ground_truth():
    truth = {}
    for path in sorted(GROUND_TRUTH_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        truth[data["program"]] = data
    return truth


def load_json(path):
    if path is None:
        return None
    p = Path(path)
    if not p.exists():
        print(f"WARNING: {p} not found", file=sys.stderr)
        return None
    return json.loads(p.read_text())


def text_similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def score_program(program, gt_rules, predicted_rules):
    predicted = [r for r in predicted_rules if r.get("program") == program]
    unmatched_gt = list(gt_rules)
    true_positives = []
    false_positives = []

    for pred in predicted:
        best_idx, best_score = None, 0.0
        for idx, gt in enumerate(unmatched_gt):
            if gt["paragraph"] != pred.get("paragraph"):
                continue
            sim = text_similarity(gt["rule_text"], pred.get("rule_text", ""))
            if sim > best_score:
                best_idx, best_score = idx, sim
        if best_idx is not None and best_score >= TEXT_MATCH_THRESHOLD:
            true_positives.append((pred, unmatched_gt.pop(best_idx), best_score))
        else:
            false_positives.append(pred)

    tp = len(true_positives)
    fp = len(false_positives)
    fn = len(unmatched_gt)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "program": program,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "missed_rules": [gt["rule_id"] for gt in unmatched_gt],
        "spurious_rules": [
            f"{p.get('paragraph')}: {p.get('rule_text', '')[:60]}" for p in false_positives
        ],
    }


def check_dead_code_leakage(predicted_rules):
    violations = []
    for rule in predicted_rules:
        dead_set = DEAD_PARAGRAPHS.get(rule.get("program", ""), set())
        if rule.get("paragraph") in dead_set:
            flagged = bool(rule.get("dead_code") or rule.get("unreachable"))
            if not flagged:
                violations.append(rule)
    return violations


def check_coverage(coverage_data):
    if not coverage_data:
        return {}
    report = {}
    for program, stats in coverage_data.items():
        total = stats.get("paragraphs_total", 0)
        processed = stats.get("paragraphs_processed", 0)
        pct = round(100 * processed / total, 1) if total else 0.0
        report[program] = {
            "paragraphs_total": total,
            "paragraphs_processed": processed,
            "coverage_pct": pct,
        }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", required=True, help="Path to submitted rules JSON")
    parser.add_argument("--coverage", help="Path to submitted coverage JSON")
    args = parser.parse_args()

    ground_truth = load_ground_truth()
    predicted_rules = load_json(args.rules) or []
    coverage_data = load_json(args.coverage)

    print("=" * 66)
    print("MAINFRAME KNOWLEDGE RECOVERY - SCORING REPORT")
    print("=" * 66)

    for program, gt in ground_truth.items():
        result = score_program(program, gt["rules"], predicted_rules)
        print(f"\n[{program}] precision={result['precision']} "
              f"recall={result['recall']} f1={result['f1']}")
        print(f"  TP={result['true_positives']} FP={result['false_positives']} "
              f"FN={result['false_negatives']}")
        if result["missed_rules"]:
            print(f"  Missed: {', '.join(result['missed_rules'])}")
        if result["spurious_rules"]:
            print("  Spurious:")
            for s in result["spurious_rules"]:
                print(f"    - {s}")

    dead_violations = check_dead_code_leakage(predicted_rules)
    print(f"\n[Dead-code check] {len(dead_violations)} violation(s)")
    for v in dead_violations:
        print(f"  - {v.get('program')}:{v.get('paragraph')} reported as live rule "
              f"but is unreachable code")

    cov = check_coverage(coverage_data)
    if cov:
        print("\n[Coverage]")
        for program, stats in cov.items():
            print(f"  {program}: {stats['coverage_pct']}% "
                  f"({stats['paragraphs_processed']}/{stats['paragraphs_total']} paragraphs)")
    else:
        print("\n[Coverage] no coverage report supplied")

    print("\n" + "=" * 66)


if __name__ == "__main__":
    main()
