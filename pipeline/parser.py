"""
parser.py - Deterministic structural parser for the fixed-format COBOL
in src/. No LLM involved. Produces, per program:

  - paragraph boundaries (line ranges)
  - the PERFORM graph between paragraphs
  - COPY includes
  - file access (READ / WRITE / REWRITE) per paragraph, resolved from
    FD/record names back to logical file names
  - the set of paragraphs reachable from the entry paragraph, and the
    complement (dead code) - this is what gates the extraction agent.

Assumes the fixture's consistent layout: division/section headers and
paragraph names at a 7-space indent, statements at 11+ spaces, comment
lines marked with '*' in column 7. This is not a general COBOL parser -
it is deliberately narrow to what this fixture actually contains
(no EXEC SQL, no inter-program CALLs), with CALL/EXEC SQL detection
left in as real, generically-written code that simply has nothing to
match in this fixture.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
COPYBOOKS_DIR = PROJECT_ROOT / "copybooks"

PARAGRAPH_RE = re.compile(r"^\s{7}([A-Z0-9][A-Z0-9-]*)\.\s*$")
PROGRAM_ID_RE = re.compile(r"^\s*PROGRAM-ID\.\s+([A-Z0-9-]+)\.?", re.IGNORECASE)
COPY_RE = re.compile(r"\bCOPY\s+([A-Z0-9-]+)\.?", re.IGNORECASE)
PERFORM_RE = re.compile(r"(?<!-)\bPERFORM\s+([A-Z0-9][A-Z0-9-]*)\b")
CALL_RE = re.compile(r"\bCALL\s+'?([A-Z0-9-]+)'?", re.IGNORECASE)
FD_RE = re.compile(r"^\s*FD\s+([A-Z0-9-]+)\.?", re.IGNORECASE)
SELECT_RE = re.compile(r"\bSELECT\s+([A-Z0-9-]+)\s+ASSIGN", re.IGNORECASE)
READ_RE = re.compile(r"\bREAD\s+([A-Z0-9-]+)\b", re.IGNORECASE)
WRITE_RE = re.compile(r"\bWRITE\s+([A-Z0-9-]+)\b", re.IGNORECASE)
REWRITE_RE = re.compile(r"\bREWRITE\s+([A-Z0-9-]+)\b", re.IGNORECASE)
EXEC_SQL_RE = re.compile(r"\bEXEC\s+SQL\b", re.IGNORECASE)
LEVEL01_RE = re.compile(r"^\s*01\s+([A-Z0-9-]+)", re.IGNORECASE)


def _strip_comment(line):
    """COBOL fixed-format: an asterisk in column 7 marks a full comment line."""
    if len(line) >= 7 and line[6] == "*":
        return ""
    return line


def _first_01_level_name(copybook_name):
    """Resolve a COPY target to the record name it defines (its first 01-level)."""
    path = COPYBOOKS_DIR / f"{copybook_name}.cpy"
    if not path.exists():
        return None
    for raw in path.read_text().splitlines():
        line = _strip_comment(raw)
        m = LEVEL01_RE.match(line)
        if m:
            return m.group(1)
    return None


def _build_file_record_map(lines):
    """
    Walk FILE-CONTROL + FILE SECTION to map each logical file name to the
    record name(s) WRITE/REWRITE statements will reference, and back.
    Returns (file_names, record_to_file).
    """
    file_names = set()
    record_to_file = {}
    current_fd = None
    in_file_section = False

    for raw in lines:
        line = _strip_comment(raw)
        stripped = line.strip()

        if stripped.upper() == "FILE SECTION.":
            in_file_section = True
            continue
        if stripped.upper() == "WORKING-STORAGE SECTION.":
            in_file_section = False

        sel = SELECT_RE.search(line)
        if sel:
            file_names.add(sel.group(1))

        if in_file_section:
            fd = FD_RE.match(line)
            if fd:
                current_fd = fd.group(1)
                file_names.add(current_fd)
                continue
            if current_fd:
                cp = COPY_RE.search(line)
                if cp:
                    record_name = _first_01_level_name(cp.group(1))
                    if record_name:
                        record_to_file[record_name] = current_fd
                    current_fd = None
                    continue
                lvl = LEVEL01_RE.match(line)
                if lvl:
                    record_to_file[lvl.group(1)] = current_fd
                    current_fd = None

    return file_names, record_to_file


def _find_paragraphs(lines, proc_div_start):
    """Return an ordered list of (name, start_idx, end_idx) - 0-based, end exclusive."""
    headers = []
    for i in range(proc_div_start, len(lines)):
        m = PARAGRAPH_RE.match(lines[i])
        if m:
            headers.append((m.group(1), i))
    paragraphs = []
    for idx, (name, start) in enumerate(headers):
        end = headers[idx + 1][1] if idx + 1 < len(headers) else len(lines)
        paragraphs.append((name, start, end))
    return paragraphs


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


def parse_program(cbl_path):
    text = Path(cbl_path).read_text()
    lines = text.splitlines()

    program_name = None
    proc_div_line = None
    copy_includes = []

    for i, raw in enumerate(lines):
        line = _strip_comment(raw)
        if program_name is None:
            m = PROGRAM_ID_RE.match(line.strip())
            if m:
                program_name = m.group(1)
        if line.strip().upper() == "PROCEDURE DIVISION.":
            proc_div_line = i
        cp = COPY_RE.search(line)
        if cp and cp.group(1) not in copy_includes:
            copy_includes.append(cp.group(1))

    if proc_div_line is None:
        raise ValueError(f"{cbl_path}: no PROCEDURE DIVISION found")

    file_names, record_to_file = _build_file_record_map(lines[:proc_div_line])
    paragraph_bounds = _find_paragraphs(lines, proc_div_line + 1)
    known_names = {name for name, _, _ in paragraph_bounds}

    paragraphs = {}
    edges = {}
    for name, start, end in paragraph_bounds:
        body_lines = [_strip_comment(l) for l in lines[start:end]]
        body_text = "\n".join(body_lines)

        performs = sorted({
            m.group(1) for m in PERFORM_RE.finditer(body_text)
            if m.group(1) in known_names
        })
        calls = sorted(set(CALL_RE.findall(body_text)))
        reads = sorted({
            record_to_file.get(m.group(1), m.group(1))
            for m in READ_RE.finditer(body_text)
            if m.group(1) in file_names
        })
        writes = sorted({
            record_to_file[m.group(1)]
            for m in WRITE_RE.finditer(body_text)
            if m.group(1) in record_to_file
        })
        rewrites = sorted({
            record_to_file[m.group(1)]
            for m in REWRITE_RE.finditer(body_text)
            if m.group(1) in record_to_file
        })
        has_sql = bool(EXEC_SQL_RE.search(body_text))

        edges[name] = performs
        paragraphs[name] = {
            "start_line": start + 1,
            "end_line": end,
            "performs": performs,
            "calls": calls,
            "file_access": {"reads": reads, "writes": writes, "rewrites": rewrites},
            "has_embedded_sql": has_sql,
            "source": "\n".join(lines[start:end]),
        }

    entry = paragraph_bounds[0][0] if paragraph_bounds else None
    reachable = _reachable_from(entry, edges) if entry else set()
    all_names = set(paragraphs)
    dead = sorted(all_names - reachable)

    return {
        "program": program_name or Path(cbl_path).stem,
        "source_file": str(Path(cbl_path).relative_to(PROJECT_ROOT)),
        "copy_includes": copy_includes,
        "entry_paragraph": entry,
        "paragraph_order": [name for name, _, _ in paragraph_bounds],
        "paragraphs": paragraphs,
        "reachable": sorted(reachable),
        "dead": dead,
        "language": "COBOL",
    }


def parse_all(src_dir=SRC_DIR):
    """All COBOL (*.cbl) and PL/I (*.pli) programs in src_dir, merged into
    one dict keyed by program name - every consumer downstream (flowchart,
    dashboard, extract.py's agent loop) just iterates this dict and never
    needs to know which language a given program is in."""
    programs = {}
    for cbl_path in sorted(src_dir.glob("*.cbl")):
        parsed = parse_program(cbl_path)
        programs[parsed["program"]] = parsed

    from pipeline.parser_pli import parse_all as parse_all_pli
    for name, parsed in parse_all_pli(src_dir).items():
        programs[name] = parsed

    return programs


if __name__ == "__main__":
    import json
    import sys

    programs = parse_all()
    for name, data in programs.items():
        print(f"{name}: {len(data['paragraph_order'])} paragraphs, "
              f"{len(data['reachable'])} reachable, {len(data['dead'])} dead "
              f"{data['dead'] if data['dead'] else ''}")

    if "--dump" in sys.argv:
        # Trim source text out of the dump - it's large and only needed at
        # extraction time, not for eyeballing the structure.
        slim = {
            name: {**data, "paragraphs": {
                p: {k: v for k, v in pdata.items() if k != "source"}
                for p, pdata in data["paragraphs"].items()
            }}
            for name, data in programs.items()
        }
        print(json.dumps(slim, indent=2))
