"""
contradict.py - Two independent checks, both deterministic (no LLM):

1. Rule-vs-wiki-page: existing_pages/*.md statements diffed against
   extracted rules by keyword overlap + numeric-literal comparison.
   Regex + word overlap is a narrow heuristic, not semantic matching -
   good enough for a 6-program fixture, not a production design.

2. Cross-program threshold drift: scans the actual COBOL (not the
   agent's rule text, which paraphrases inconsistently - see
   check_threshold_drift's docstring for why that distinction matters)
   for 'IF <field> <op> <value>' comparisons, resolves WORKING-STORAGE
   constants to their literal VALUE, and flags the same field+value
   compared with a different operator in two different programs' live
   code - the DEPOSIT-vs-ACCTMSTR fee-waiver boundary drift.
"""

import json
import re
import sys
from pathlib import Path

from pipeline.parser import PROJECT_ROOT, parse_all
from pipeline.fields import build_field_index

EXISTING_PAGES_DIR = PROJECT_ROOT / "existing_pages"

NUMBER_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")
STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "of", "and", "or", "if", "this",
    "for", "in", "on", "by", "with", "its", "than", "or", "as", "be",
    "account", "accounts", "balance", "field", "rule", "rules",
}


def _normalize_number(tok):
    return tok.replace("$", "").replace(",", "").rstrip(".")


def _significant_words(text):
    words = re.findall(r"[a-z']+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def _extract_page_statements(md_path):
    """Pull numbered/bulleted rule-like lines out of a wiki markdown page."""
    statements = []
    for raw in Path(md_path).read_text().splitlines():
        line = raw.strip()
        if re.match(r"^(\d+\.|-|\*)\s+", line):
            text = re.sub(r"^(\d+\.|-|\*)\s+", "", line)
            text = re.sub(r"\*\*", "", text)
            statements.append(text)
    return statements


def _best_match(statement, candidate_rules):
    stmt_words = _significant_words(statement)
    if not stmt_words:
        return None, 0.0
    best_rule, best_score = None, 0.0
    for rule in candidate_rules:
        rule_words = _significant_words(rule.get("rule_text", ""))
        if not rule_words:
            continue
        overlap = stmt_words & rule_words
        score = len(overlap) / len(stmt_words | rule_words)
        if score > best_score:
            best_rule, best_score = rule, score
    return best_rule, best_score

MATCH_THRESHOLD = 0.28

VALUE_CONST_RE = re.compile(
    r"^\s*\d{2}\s+([A-Z0-9-]+)\s+PIC\s+\S+.*?VALUE\s+(-?\d+(?:\.\d+)?)", re.IGNORECASE
)
IF_COMPARISON_RE = re.compile(
    r"\bIF\s+([A-Z][A-Z0-9-]*)\s*(>=|<=|>|<|=)\s*([A-Z0-9][A-Z0-9-]*)\b"
)


def _strip_comment(line):
    if len(line) >= 7 and line[6] == "*":
        return ""
    return line


def _parse_working_storage_constants(cbl_path):
    """VALUE-clause constants, e.g. 01 WS-FEE-WAIVER-THRESHOLD ... VALUE 500.00."""
    consts = {}
    for raw in Path(cbl_path).read_text().splitlines():
        m = VALUE_CONST_RE.match(_strip_comment(raw))
        if m:
            consts[m.group(1)] = m.group(2)
    return consts


def check_threshold_drift(programs):
    """
    Fully deterministic - no dependency on how the extraction agent
    phrased anything. Scans every reachable paragraph's actual COBOL for
    'IF <field> <op> <operand>' comparisons, resolves any operand that's
    a named WORKING-STORAGE constant to its literal VALUE, then flags
    when the same field is compared to the same literal with a
    DIFFERENT operator in two different programs' live code - e.g.
    DEPOSIT's 'IF ACCT-BALANCE >= WS-FEE-WAIVER-THRESHOLD' (500.00)
    against ACCTMSTR's 'IF ACCT-BALANCE > WS-FEE-WAIVER-THRESHOLD'
    (also 500.00, different operator).
    """
    entries = []
    for name, data in programs.items():
        consts = _parse_working_storage_constants(PROJECT_ROOT / data["source_file"])
        for para in data["reachable"]:
            source = data["paragraphs"][para]["source"]
            for m in IF_COMPARISON_RE.finditer(source):
                field, op, operand = m.groups()
                resolved = consts.get(operand, operand)
                try:
                    value = float(resolved)
                except ValueError:
                    continue
                entries.append({"program": name, "paragraph": para,
                                 "field": field, "operator": op, "value": value})

    drifts = []
    seen = set()
    for i, a in enumerate(entries):
        for b in entries[i + 1:]:
            if a["program"] == b["program"]:
                continue
            if a["field"] != b["field"] or a["value"] != b["value"]:
                continue
            if a["operator"] == b["operator"]:
                continue
            key = tuple(sorted([f"{a['program']}:{a['paragraph']}:{a['operator']}",
                                 f"{b['program']}:{b['paragraph']}:{b['operator']}"]))
            if key in seen:
                continue
            seen.add(key)
            drifts.append({
                "field": a["field"],
                "value": a["value"],
                "a": {"program": a["program"], "paragraph": a["paragraph"], "operator": a["operator"]},
                "b": {"program": b["program"], "paragraph": b["paragraph"], "operator": b["operator"]},
            })
    return drifts


def check_numeric_contradictions(rules_by_program):
    contradictions = []
    for md_path in sorted(EXISTING_PAGES_DIR.glob("*.md")):
        text = md_path.read_text()
        m = re.search(r"\*\*Program:\*\*\s*(\S+)", text)
        if not m:
            continue
        program = m.group(1).replace(".cbl", "")
        candidate_rules = rules_by_program.get(program, [])
        if not candidate_rules:
            continue

        for statement in _extract_page_statements(md_path):
            page_numbers = {_normalize_number(n) for n in NUMBER_RE.findall(statement)}
            if not page_numbers:
                continue
            rule, score = _best_match(statement, candidate_rules)
            if not rule or score < MATCH_THRESHOLD:
                continue
            rule_numbers = {_normalize_number(n) for n in NUMBER_RE.findall(rule.get("rule_text", ""))}
            if rule_numbers and page_numbers != rule_numbers:
                contradictions.append({
                    "page": md_path.name,
                    "program": program,
                    "page_statement": statement,
                    "page_numbers": sorted(page_numbers),
                    "matched_rule_id": rule.get("rule_id"),
                    "matched_rule_text": rule.get("rule_text"),
                    "code_numbers": sorted(rule_numbers),
                    "match_confidence": round(score, 2),
                })
    return contradictions


def check_redefines_contradictions(field_index=None):
    """Catch a page describing a REDEFINES field as 'independent'."""
    field_index = field_index or build_field_index()
    contradictions = []
    for md_path in sorted(EXISTING_PAGES_DIR.glob("*.md")):
        text = md_path.read_text()
        for line in text.splitlines():
            m = re.search(r"`([A-Z0-9-]+)`.*\b(independent|unrelated)\b", line, re.IGNORECASE)
            if not m:
                continue
            field = m.group(1)
            equiv = set(field_index["equivalence"].get(field, [field]))
            if len(equiv) > 1:
                contradictions.append({
                    "page": md_path.name,
                    "page_statement": line.strip(),
                    "field": field,
                    "actual_equivalence_class": sorted(equiv),
                    "reason": f"{field} is described as independent/unrelated but "
                              f"physically shares storage (REDEFINES) with "
                              f"{', '.join(sorted(equiv - {field}))}.",
                })
    return contradictions


def find_contradictions(rules, programs=None):
    by_program = {}
    for r in rules:
        by_program.setdefault(r.get("program"), []).append(r)
    numeric = check_numeric_contradictions(by_program)
    redefines = check_redefines_contradictions()
    threshold_drift = check_threshold_drift(programs or parse_all())
    return {
        "numeric_contradictions": numeric,
        "field_relationship_contradictions": redefines,
        "threshold_drift": threshold_drift,
    }


def main():
    if len(sys.argv) < 2:
        print("usage: python -m pipeline.contradict output/rules.json")
        sys.exit(1)
    rules = json.loads(Path(sys.argv[1]).read_text())
    result = find_contradictions(rules)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
