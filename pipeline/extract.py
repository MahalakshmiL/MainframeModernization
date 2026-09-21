"""
extract.py - Agentic chunked rule extraction. This is the one piece of
the pipeline that actually calls an LLM. Requires ANTHROPIC_API_KEY.

Claude is given four tools over the deterministic layer (parser.py +
fields.py) and walks each program's reachable paragraphs itself: pull
a paragraph, reason about it, optionally check which fields it
touches, and emit_rule() for each atomic business rule it finds.
emit_rule() rejects (with a message the model sees and can act on)
any citation to a paragraph that isn't in the program's reachable
set, or an empty rule_text - so a rule that fails those checks never
makes it into rules.json; it's retried or dropped by the model, not
filtered out afterwards.

Coverage is tracked independently of what the model claims: every
get_paragraph_source() call is logged, so coverage.json reports what
was ACTUALLY read, not what the model says it read.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from pipeline.parser import parse_all, PROJECT_ROOT
from pipeline.fields import build_field_index
from pipeline.env import load_dotenv

DEFAULT_MODEL = os.environ.get("EXTRACT_MODEL", "claude-sonnet-5")
MAX_TOOL_ITERATIONS = 60

SYSTEM_PROMPT = """You are recovering business rules from legacy COBOL for a bank's \
core deposit/account-servicing system. You will be given one program at a time.

Ground rules, no exceptions:
1. Call get_reachable_paragraphs first. Only paragraphs it returns are live code \
that reached the program's entry point - anything else is dead code and must \
never be cited as a current business rule.
2. For every paragraph in that list, call get_paragraph_source to read it before \
saying anything about what it does. Do not guess from the paragraph name.
3. Call get_field_touches for a paragraph when the rule you're about to write \
depends on which fields it reads or writes - the tool will also tell you if a \
field shares physical storage with another field via REDEFINES, which changes \
what "read" or "write" means for it.
4. Call emit_rule once per atomic business rule, in plain language a bank \
business analyst (not a programmer) would understand - no COBOL keywords, no \
paragraph-internal variable names unless a person outside IT would recognize \
them. Every emit_rule call must name the exact paragraph the rule came from.
5. If a paragraph is purely mechanical (open/close a file, a loop control \
variable) and contains no business rule, skip it - do not invent a rule to \
fill a quota.
6. When you have processed every reachable paragraph, say so in plain text and \
stop calling tools.
"""

TOOLS = [
    {
        "name": "get_reachable_paragraphs",
        "description": "Return the list of paragraph names in this program that "
                        "are actually reachable from its entry point (i.e. not "
                        "dead code).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_paragraph_source",
        "description": "Return the COBOL source text of one paragraph in the "
                        "current program.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paragraph": {"type": "string",
                              "description": "Exact paragraph name, e.g. 3100-CHECK-FEE-WAIVER"},
            },
            "required": ["paragraph"],
        },
    },
    {
        "name": "get_field_touches",
        "description": "Return which copybook fields a paragraph reads/writes, "
                        "and any REDEFINES relationship those fields have with "
                        "other fields.",
        "input_schema": {
            "type": "object",
            "properties": {"paragraph": {"type": "string"}},
            "required": ["paragraph"],
        },
    },
    {
        "name": "emit_rule",
        "description": "Record one atomic business rule extracted from a "
                        "specific paragraph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paragraph": {"type": "string",
                              "description": "Exact paragraph this rule came from."},
                "rule_text": {"type": "string",
                              "description": "The rule in plain business language."},
            },
            "required": ["paragraph", "rule_text"],
        },
    },
]


class ProgramSession:
    """Holds the tool-execution state (and coverage tracking) for one program."""

    def __init__(self, program_name, parsed_program, field_index):
        self.program_name = program_name
        self.parsed = parsed_program
        self.field_index = field_index
        self.paragraphs_read = set()
        self.rules = []
        self.rejections = []

    def call_tool(self, name, tool_input):
        if name == "get_reachable_paragraphs":
            return {"reachable_paragraphs": self.parsed["reachable"]}

        if name == "get_paragraph_source":
            para = tool_input.get("paragraph", "")
            if para not in self.parsed["reachable"]:
                return {"error": f"'{para}' is not in the reachable-paragraph set "
                                  f"for {self.program_name}. It is either dead code "
                                  f"or does not exist. Call get_reachable_paragraphs "
                                  f"to see valid names."}
            self.paragraphs_read.add(para)
            return {"paragraph": para, "source": self.parsed["paragraphs"][para]["source"]}

        if name == "get_field_touches":
            para = tool_input.get("paragraph", "")
            if para not in self.parsed["paragraphs"]:
                return {"error": f"unknown paragraph '{para}'"}
            touches = []
            for field, data in self.field_index["fields"].items():
                reads = [t for t in self.field_index["touches"][field]["reads"]
                         if t["program"] == self.program_name and t["paragraph"] == para]
                writes = [t for t in self.field_index["touches"][field]["writes"]
                          if t["program"] == self.program_name and t["paragraph"] == para]
                if reads or writes:
                    equiv = self.field_index["equivalence"].get(field, [field])
                    touches.append({
                        "field": field,
                        "access": "write" if writes else "read",
                        "shares_storage_with": [f for f in equiv if f != field],
                        "db2_column": data["db2_column"],
                    })
            return {"paragraph": para, "fields": touches}

        if name == "emit_rule":
            para = tool_input.get("paragraph", "")
            text = (tool_input.get("rule_text") or "").strip()
            if para not in self.parsed["reachable"]:
                msg = (f"REJECTED: '{para}' is not a reachable paragraph in "
                       f"{self.program_name}. A rule cannot be cited to dead or "
                       f"nonexistent code.")
                self.rejections.append({"paragraph": para, "rule_text": text, "reason": msg})
                return {"accepted": False, "reason": msg}
            if not text:
                msg = "REJECTED: rule_text is empty."
                self.rejections.append({"paragraph": para, "rule_text": text, "reason": msg})
                return {"accepted": False, "reason": msg}
            rule_id = f"{self.program_name}-A{len(self.rules) + 1}"
            citation = f"{self.parsed['source_file']}:{para}"
            self.rules.append({
                "rule_id": rule_id,
                "program": self.program_name,
                "paragraph": para,
                "citation": citation,
                "rule_text": text,
            })
            return {"accepted": True, "rule_id": rule_id}

        return {"error": f"unknown tool '{name}'"}

    def coverage(self):
        total = len(self.parsed["reachable"])
        processed = len(self.paragraphs_read & set(self.parsed["reachable"]))
        return {
            "paragraphs_total": total,
            "paragraphs_processed": processed,
            "coverage_pct": round(100 * processed / total, 1) if total else 0.0,
            "paragraphs_skipped": sorted(set(self.parsed["reachable"]) - self.paragraphs_read),
        }


def run_extraction_for_program(client, model, program_name, parsed_program, field_index, verbose=True):
    session = ProgramSession(program_name, parsed_program, field_index)
    messages = [{
        "role": "user",
        "content": f"Extract business rules from program {program_name} "
                    f"({parsed_program['source_file']}). Start by calling "
                    f"get_reachable_paragraphs.",
    }]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            if verbose:
                text = "".join(b.text for b in response.content if b.type == "text")
                print(f"  [{program_name}] agent stopped: {text[:200]}")
            break

        tool_results = []
        for block in tool_uses:
            result = session.call_tool(block.name, block.input)
            if verbose:
                print(f"  [{program_name}] {block.name}({block.input}) -> {str(result)[:120]}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})
    else:
        if verbose:
            print(f"  [{program_name}] hit MAX_TOOL_ITERATIONS, stopping")

    return session


def main():
    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument("--model", default=DEFAULT_MODEL)
    argp.add_argument("--program", help="Only extract this one program (default: all)")
    argp.add_argument("--out-rules", default=str(PROJECT_ROOT / "output" / "rules.json"))
    argp.add_argument("--out-coverage", default=str(PROJECT_ROOT / "output" / "coverage.json"))
    argp.add_argument("--runs", type=int, default=1,
                       help="Run extraction N times and keep each run's output "
                            "separately (rules.run1.json, rules.run2.json, ...) - "
                            "for the variance-between-runs check the spec's demo "
                            "bar asks for.")
    args = argp.parse_args()

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set. This is the one part of the "
              "pipeline that calls the Claude API - get a key at "
              "console.anthropic.com, then `export ANTHROPIC_API_KEY=sk-ant-...`.",
              file=sys.stderr)
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("ERROR: the 'anthropic' package is not installed. "
              "Run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    client_kwargs = {}
    if workspace_id:
        client_kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id}
    client = anthropic.Anthropic(**client_kwargs)
    programs = parse_all()
    field_index = build_field_index()

    if args.program:
        if args.program not in programs:
            print(f"ERROR: unknown program '{args.program}'. Known: {sorted(programs)}",
                  file=sys.stderr)
            sys.exit(1)
        programs = {args.program: programs[args.program]}

    for run in range(1, args.runs + 1):
        all_rules, all_coverage, all_rejections = [], {}, {}
        for name, parsed in programs.items():
            print(f"Extracting {name} (run {run}/{args.runs})...")
            try:
                session = run_extraction_for_program(client, args.model, name, parsed, field_index)
            except anthropic.BadRequestError as e:
                if "workspace" in str(e).lower():
                    print("ERROR: this API key needs a workspace ID. Add "
                          "ANTHROPIC_WORKSPACE_ID=<your workspace id> to .env "
                          "(console.anthropic.com -> Settings -> Workspaces) and re-run.",
                          file=sys.stderr)
                else:
                    print(f"ERROR calling the API: {e}", file=sys.stderr)
                sys.exit(1)
            all_rules.extend(session.rules)
            all_coverage[name] = session.coverage()
            if session.rejections:
                all_rejections[name] = session.rejections

        suffix = "" if args.runs == 1 else f".run{run}"
        rules_path = Path(args.out_rules).with_suffix(f"{suffix}.json") if suffix else Path(args.out_rules)
        coverage_path = Path(args.out_coverage).with_suffix(f"{suffix}.json") if suffix else Path(args.out_coverage)
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        rules_path.write_text(json.dumps(all_rules, indent=2))
        coverage_path.write_text(json.dumps(all_coverage, indent=2))
        print(f"Run {run}: {len(all_rules)} rules -> {rules_path}")
        if all_rejections:
            rej_path = rules_path.parent / f"rejections{suffix}.json"
            rej_path.write_text(json.dumps(all_rejections, indent=2))
            total_rej = sum(len(v) for v in all_rejections.values())
            print(f"Run {run}: {total_rej} rejected emit_rule call(s) -> {rej_path}")


if __name__ == "__main__":
    main()
