"""
fields.py - Copybook field index. No LLM involved.

Parses copybooks/*.cpy for the field hierarchy, groups fields that
physically share storage via REDEFINES into equivalence classes, maps
each field to its DB2 column (via DDLACCT.sql), and scans every
program's paragraph source (from parser.py) for reads/writes of each
field.

The REDEFINES handling is the point of this module: ACCT-INT-RATE and
ACCT-FEE-CODE are two different names for the same bytes. Any question
about "who touches this field" has to be answered for the whole
equivalence class, not just the one name that was asked about.
"""

import re
from pathlib import Path

from pipeline.parser import parse_all, PROJECT_ROOT, COPYBOOKS_DIR

DDL_PATH = PROJECT_ROOT / "src" / "DDLACCT.sql"

LEVEL_RE = re.compile(r"^\s*(\d{2})\s+([A-Z0-9-]+)(.*)$", re.IGNORECASE)
REDEFINES_RE = re.compile(r"\bREDEFINES\s+([A-Z0-9-]+)", re.IGNORECASE)
PIC_RE = re.compile(r"\bPIC(?:TURE)?\b", re.IGNORECASE)
DDL_COLUMN_RE = re.compile(r"^\s*([A-Z0-9_]+)\s+[A-Z]", re.IGNORECASE)


def _strip_comment(line):
    if len(line) >= 7 and line[6] == "*":
        return ""
    return line


class _Node:
    def __init__(self, level, name, redefines=None):
        self.level = level
        self.name = name
        self.redefines = redefines
        self.children = []
        self.parent = None

    def is_elementary(self):
        return not self.children

    def leaves(self):
        if self.is_elementary():
            return [self.name]
        out = []
        for c in self.children:
            out.extend(c.leaves())
        return out


def _parse_copybook_tree(path):
    """Parse one .cpy file into a forest of _Node trees keyed by level number nesting."""
    roots = []
    stack = []  # (node) in scope order, top = current deepest

    for raw in Path(path).read_text().splitlines():
        line = _strip_comment(raw)
        m = LEVEL_RE.match(line)
        if not m:
            continue
        level_str, name, rest = m.groups()
        level = int(level_str)
        if level == 88:
            continue  # condition names aren't storage
        redef = REDEFINES_RE.search(rest)
        node = _Node(level, name, redef.group(1) if redef else None)

        while stack and stack[-1].level >= level:
            stack.pop()
        if stack:
            node.parent = stack[-1]
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)

    return roots


def _redefines_equivalence(roots):
    """
    Build equivalence classes of field names that share physical storage.
    A node with REDEFINES X is unioned with the node named X at the same
    level, and their leaf fields become mutually equivalent.
    """
    by_name = {}

    def index(node):
        by_name[node.name] = node
        for c in node.children:
            index(c)

    for r in roots:
        index(r)

    classes = {}  # name -> set of equivalent names

    def cls_of(name):
        return classes.setdefault(name, {name})

    for node in by_name.values():
        if node.redefines and node.redefines in by_name:
            target = by_name[node.redefines]
            group_a = cls_of(node.name)
            group_b = cls_of(target.name)
            merged = group_a | group_b
            leaves_a = node.leaves()
            leaves_b = target.leaves()
            all_leaves = set(leaves_a) | set(leaves_b)
            for leaf in all_leaves:
                classes[leaf] = all_leaves | merged

    return classes


def _parse_ddl_columns():
    """DDLACCT.sql -> {DB2_COLUMN_NAME: table_name}."""
    columns = {}
    table = None
    if not DDL_PATH.exists():
        return columns
    for raw in DDL_PATH.read_text().splitlines():
        line = raw.strip()
        if line.upper().startswith("CREATE TABLE"):
            table = line.split()[2]
            continue
        if table and line and not line.startswith("--") and line[0] not in ")(,":
            m = DDL_COLUMN_RE.match(line)
            if m and m.group(1).upper() not in {"PRIMARY", "FOREIGN", "CONSTRAINT"}:
                columns[m.group(1).upper()] = table
        if line.startswith(");"):
            table = None
    return columns


def _cobol_to_db2_column(field_name):
    return field_name.replace("-", "_").upper()


def build_field_index(src_dir=None):
    programs = parse_all(src_dir) if src_dir else parse_all()
    ddl_columns = _parse_ddl_columns()

    all_fields = {}       # field_name -> {"copybook":..., "pic": bool}
    equivalence = {}       # field_name -> sorted list of equivalent names

    for cpy_path in sorted(COPYBOOKS_DIR.glob("*.cpy")):
        roots = _parse_copybook_tree(cpy_path)
        eq = _redefines_equivalence(roots)
        for name, group in eq.items():
            equivalence[name] = sorted(group)

        def walk(node):
            if node.is_elementary():
                all_fields[node.name] = {
                    "copybook": cpy_path.stem,
                    "db2_column": _cobol_to_db2_column(node.name),
                    "db2_table": ddl_columns.get(_cobol_to_db2_column(node.name)),
                }
            for c in node.children:
                walk(c)

        for r in roots:
            walk(r)

    # Reads/writes per field, scanning every program's paragraph source.
    touches = {name: {"reads": [], "writes": []} for name in all_fields}
    write_pat = {}
    for field in all_fields:
        esc = re.escape(field)
        write_pat[field] = re.compile(
            rf"\b(?:TO|FROM)\s+{esc}\b|\bCOMPUTE\s+{esc}\b", re.IGNORECASE
        )
    read_pat = {
        field: re.compile(rf"\b{re.escape(field)}\b", re.IGNORECASE)
        for field in all_fields
    }

    for prog_name, prog in programs.items():
        for para_name, para in prog["paragraphs"].items():
            # Strip comment lines before matching - a field named in a
            # trailing doc comment (which COBOL's fixed format can attach
            # to the wrong paragraph body) is not an actual code access.
            source = "\n".join(
                _strip_comment(l) for l in para["source"].splitlines()
            )
            for field in all_fields:
                if not read_pat[field].search(source):
                    continue
                site = {"program": prog_name, "paragraph": para_name,
                        "reachable": para_name in prog["reachable"]}
                if write_pat[field].search(source):
                    touches[field]["writes"].append(site)
                else:
                    touches[field]["reads"].append(site)

    return {
        "fields": all_fields,
        "equivalence": equivalence,
        "touches": touches,
    }


if __name__ == "__main__":
    import json
    import sys

    index = build_field_index()
    print(f"{len(index['fields'])} fields indexed")
    redefined = {k: v for k, v in index["equivalence"].items() if len(v) > 1}
    print(f"REDEFINES equivalence classes: {redefined}")

    if "--dump" in sys.argv:
        print(json.dumps(index, indent=2))
