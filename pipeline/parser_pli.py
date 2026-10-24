"""
parser_pli.py - Deterministic structural parser for the free-format
PL/I source in src/*.pli. No LLM involved. Produces the exact same
output shape as parser.py's parse_program() (paragraph_order,
paragraphs{performs, file_access, source}, reachable, dead,
entry_paragraph) so everything downstream that already consumes that
shape generically - flowchart.py, dashboard.py's coverage/dead-code
accounting, extract.py's agent loop - picks up a PL/I program with no
changes at all. A "paragraph" here is a PL/I procedure; the key name
stayed "paragraph" rather than being renamed, precisely so the rest
of the pipeline doesn't need to know which language it's looking at.

Assumes the fixture's consistent style: free-format PL/I, one
statement per line, comments only as /* ... */ on their own lines,
procedures declared as `LABEL: PROCEDURE ...;` / `END LABEL;` with at
most one level of nesting (internal procedures declared as flat
siblings after the external procedure's own executable statements,
which is how this fixture - and most real PL/I - is written). This is
not a general PL/I parser, same spirit as parser.py's own docstring.

Scope note: this does NOT build a REDEFINES-equivalent field index
the way fields.py does for COBOL (that's tree-based, level-number
parsing specific to COBOL copybooks). It does detect the DEFINED
attribute (PL/I's REDEFINES-analog, a structure overlaying another's
storage) and reports the overlay pairs it finds, but that detection
isn't wired into lineage.py's cross-language field-impact answers -
a real next step, not pretended to be done here.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
COPYBOOKS_DIR = PROJECT_ROOT / "copybooks"

PROC_START_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*:\s*PROCEDURE\b", re.IGNORECASE)
PROC_END_RE = re.compile(r"^\s*END\s+([A-Z][A-Z0-9_]*)\s*;", re.IGNORECASE)
MAIN_OPT_RE = re.compile(r"OPTIONS\s*\(\s*MAIN\s*\)", re.IGNORECASE)
CALL_RE = re.compile(r"\bCALL\s+([A-Z][A-Z0-9_]*)\b", re.IGNORECASE)
INCLUDE_RE = re.compile(r"%INCLUDE\s+([A-Z][A-Z0-9_]*)\s*;", re.IGNORECASE)
READ_RE = re.compile(r"\bREAD\s+FILE\s*\(\s*([A-Z][A-Z0-9_]*)\s*\)", re.IGNORECASE)
WRITE_RE = re.compile(r"\bWRITE\s+FILE\s*\(\s*([A-Z][A-Z0-9_]*)\s*\)", re.IGNORECASE)
DEFINED_RE = re.compile(
    r"^\s*DCL\s+\d+\s+([A-Z][A-Z0-9_]*)\s+DEFINED\s+([A-Z][A-Z0-9_]*)", re.IGNORECASE
)


def _strip_comment_block(text):
    """PL/I /* ... */ comments, possibly spanning lines. No nesting."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _find_procedures(lines):
    """Stack-based scan -> list of dicts: name, start, end (0-based, end inclusive), children."""
    stack = []
    procedures = []
    by_name = {}

    for i, line in enumerate(lines):
        clean = _strip_comment_block(line)
        start_m = PROC_START_RE.match(clean)
        if start_m:
            name = start_m.group(1)
            entry = {"name": name, "start": i, "end": None, "children": [],
                      "is_main": bool(MAIN_OPT_RE.search(clean))}
            if stack:
                stack[-1]["children"].append(entry)
            stack.append(entry)
            procedures.append(entry)
            by_name[name.upper()] = entry
            continue
        end_m = PROC_END_RE.match(clean)
        if end_m and stack and end_m.group(1).upper() == stack[-1]["name"].upper():
            stack[-1]["end"] = i
            stack.pop()

    return procedures


def _own_body_range(proc):
    """(start, end) 0-based inclusive range for THIS procedure's own statements,
    excluding any nested children's text."""
    if proc["children"]:
        first_child_start = min(c["start"] for c in proc["children"])
        return proc["start"], first_child_start - 1
    return proc["start"], proc["end"]


def _reachable_from(entry, edges):
    seen = set()
    stack = [entry]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        for target in edges.get(node, ()):
            if target not in seen:
                stack.append(target)
    return seen


def parse_program(pli_path):
    pli_path = Path(pli_path)
    text = pli_path.read_text()
    lines = text.splitlines()

    program_name = pli_path.stem.upper()
    includes = []
    for raw in lines:
        m = INCLUDE_RE.search(_strip_comment_block(raw))
        if m and m.group(1) not in includes:
            includes.append(m.group(1))

    procedures = _find_procedures(lines)
    known_names = {p["name"] for p in procedures}
    main_proc = next((p for p in procedures if p["is_main"]), procedures[0] if procedures else None)
    if main_proc is None:
        raise ValueError(f"{pli_path}: no PROCEDURE found")

    defined_equivalence = []
    for raw in lines:
        m = DEFINED_RE.match(_strip_comment_block(raw))
        if m:
            defined_equivalence.append({"overlay": m.group(1), "base": m.group(2)})

    paragraphs = {}
    edges = {}
    for proc in procedures:
        own_start, own_end = _own_body_range(proc)
        own_start = max(own_start, 0)
        own_end = max(own_end, own_start)
        own_text = "\n".join(_strip_comment_block(l) for l in lines[own_start:own_end + 1])

        performs = sorted({
            m.group(1) for m in CALL_RE.finditer(own_text) if m.group(1) in known_names
        })
        reads = sorted({m.group(1) for m in READ_RE.finditer(own_text)})
        writes = sorted({m.group(1) for m in WRITE_RE.finditer(own_text)})

        edges[proc["name"]] = performs
        full_text = "\n".join(lines[proc["start"]:proc["end"] + 1])
        paragraphs[proc["name"]] = {
            "start_line": proc["start"] + 1,
            "end_line": proc["end"] + 1,
            "performs": performs,
            "calls": [],
            "file_access": {"reads": reads, "writes": writes, "rewrites": []},
            "has_embedded_sql": False,
            "source": full_text,
        }

    reachable = _reachable_from(main_proc["name"], edges)
    all_names = set(paragraphs)
    dead = sorted(all_names - reachable)

    return {
        "program": program_name,
        "source_file": str(pli_path.relative_to(PROJECT_ROOT)),
        "copy_includes": includes,
        "entry_paragraph": main_proc["name"],
        "paragraph_order": [p["name"] for p in procedures],
        "paragraphs": paragraphs,
        "reachable": sorted(reachable),
        "dead": dead,
        "language": "PL/I",
        "defined_equivalence": defined_equivalence,
    }


def parse_all(src_dir=SRC_DIR):
    programs = {}
    for pli_path in sorted(Path(src_dir).glob("*.pli")):
        parsed = parse_program(pli_path)
        programs[parsed["program"]] = parsed
    return programs


if __name__ == "__main__":
    import json
    import sys

    programs = parse_all()
    for name, data in programs.items():
        print(f"{name} ({data['language']}): {len(data['paragraph_order'])} procedures, "
              f"{len(data['reachable'])} reachable, {len(data['dead'])} dead "
              f"{data['dead'] if data['dead'] else ''}")
        if data["defined_equivalence"]:
            print(f"  DEFINED overlays: {data['defined_equivalence']}")

    if "--dump" in sys.argv:
        slim = {
            name: {**data, "paragraphs": {
                p: {k: v for k, v in pdata.items() if k != "source"}
                for p, pdata in data["paragraphs"].items()
            }}
            for name, data in programs.items()
        }
        print(json.dumps(slim, indent=2))
