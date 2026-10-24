"""
flowchart.py - Auto-layout for a per-program paragraph flowchart,
computed from the real PERFORM graph in parser.py. No hand-plotted
coordinates: BFS distance from the entry paragraph becomes the row
(level), paragraphs within a level keep their source order left to
right, and dead (unreachable) paragraphs get their own row at the
bottom, visually separated from the live flow rather than positioned
as if they were part of it.

Produces plain coordinate data (JSON-serializable) - the dashboard's
JS draws the actual SVG from these numbers, so the layout math lives
in one place and is easy to sanity-check by just printing it.
"""

from pipeline.parser import parse_all

BOX_W = 176
BOX_H = 46
COL_GAP = 20
ROW_GAP = 46
MARGIN = 24
DEAD_GAP = 44


def _bfs_levels(entry, edge_map, reachable):
    level = {entry: 0}
    order = [entry]
    i = 0
    while i < len(order):
        node = order[i]
        i += 1
        for target in edge_map.get(node, []):
            if target not in level:
                level[target] = level[node] + 1
                order.append(target)
    # Any reachable paragraph the BFS didn't hit (shouldn't happen, since
    # parser.py's own reachability walk uses the same edges) falls back to
    # level 0 rather than being silently dropped.
    for n in reachable:
        if n not in level:
            level[n] = 0
    return level


def build_program_flow(parsed_program):
    paragraphs = parsed_program["paragraphs"]
    reachable = parsed_program["reachable"]
    dead = parsed_program["dead"]
    entry = parsed_program["entry_paragraph"]
    order = parsed_program["paragraph_order"]

    edges_raw = []
    for name in reachable:
        for target in paragraphs[name]["performs"]:
            if target in reachable:
                edges_raw.append((name, target))

    edge_map = {}
    for src, tgt in edges_raw:
        edge_map.setdefault(src, []).append(tgt)

    levels = _bfs_levels(entry, edge_map, reachable)

    by_level = {}
    for name in order:
        if name in reachable:
            by_level.setdefault(levels[name], []).append(name)

    max_level = max(by_level) if by_level else 0
    max_cols = max((len(v) for v in by_level.values()), default=1)
    width = max(MARGIN * 2 + max_cols * BOX_W + max(max_cols - 1, 0) * COL_GAP, 420)

    positions = {}
    for lvl in range(max_level + 1):
        names = by_level.get(lvl, [])
        n = len(names)
        if not n:
            continue
        row_width = n * BOX_W + (n - 1) * COL_GAP
        start_x = (width - row_width) / 2
        y = MARGIN + lvl * (BOX_H + ROW_GAP)
        for i, name in enumerate(names):
            x = start_x + i * (BOX_W + COL_GAP)
            positions[name] = {"x": round(x, 1), "y": round(y, 1), "w": BOX_W, "h": BOX_H}

    live_bottom = MARGIN + (max_level + 1) * (BOX_H + ROW_GAP) - ROW_GAP

    dead_row_y = None
    if dead:
        dead_row_y = round(live_bottom + DEAD_GAP, 1)
        n_dead = len(dead)
        row_width = n_dead * BOX_W + (n_dead - 1) * COL_GAP
        start_x = (width - row_width) / 2
        for i, name in enumerate(dead):
            positions[name] = {"x": round(start_x + i * (BOX_W + COL_GAP), 1),
                                "y": dead_row_y, "w": BOX_W, "h": BOX_H}

    total_height = round((dead_row_y + BOX_H + MARGIN) if dead_row_y else (live_bottom + MARGIN), 1)

    nodes = []
    for name in order:
        if name not in positions:
            continue
        pos = positions[name]
        nodes.append({
            "name": name,
            "x": pos["x"], "y": pos["y"], "w": pos["w"], "h": pos["h"],
            "dead": name in dead,
            "entry": name == entry,
        })

    edges = [{"from": s, "to": t} for s, t in edges_raw]

    return {
        "program": parsed_program["program"],
        "entry": entry,
        "width": round(width, 1),
        "height": total_height,
        "nodes": nodes,
        "edges": edges,
        "dead_row_y": dead_row_y,
    }


def build_all_flows():
    programs = parse_all()
    return {name: build_program_flow(data) for name, data in programs.items()}


if __name__ == "__main__":
    flows = build_all_flows()
    for name, f in flows.items():
        print(f"{name}: {len(f['nodes'])} nodes, {len(f['edges'])} edges, "
              f"canvas {f['width']}x{f['height']}")
