"""
confluence_preview.py - Renders the Confluence wiki-markup page that
wiki.py generates (output/wiki_page.confluence) as a readable HTML
preview. No LLM involved, no real Confluence connection - there's no
Atlassian account to publish to in this environment (see .mcp.json's
atlassian entry, parked for whenever one exists), so this is the
honest stand-in: what the generated page's content actually says,
rendered legibly, in this project's own design system rather than a
pretend screenshot of the real Confluence UI.
"""

import html
import re
from pathlib import Path

from pipeline.parser import PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "output"

INFO_RE = re.compile(r"^\{info:title=([^}]*)\}(.*)\{info\}$")
NOTE_RE = re.compile(r"^\{note:title=([^}]*)\}(.*)\{note\}$")
STATUS_RE = re.compile(r"\{status:colour=([A-Za-z]+)\|title=([^}]*)\}")

STATUS_COLOR_MAP = {
    "yellow": "warn",
    "green": "good",
    "red": "bad",
    "grey": "ink-soft",
    "gray": "ink-soft",
}


def _esc(s):
    return html.escape(s, quote=True)


def _render_inline(text):
    """Bold (*text*), code-ish citations already plain, and the status macro."""
    text = _esc(text)

    def status_sub(m):
        colour = m.group(1).lower()
        label = _esc(m.group(2))
        token = STATUS_COLOR_MAP.get(colour, "accent")
        return f'<span class="lozenge {token}">{label}</span>'

    text = STATUS_RE.sub(status_sub, text)
    text = re.sub(r"\*([^*]+)\*", r"<b>\1</b>", text)
    return text


MACRO_RE = re.compile(r"\{[^{}]*\}")


def _split_cells(row):
    """Split a Confluence table row on unescaped | (cells may contain \\|).
    A macro like {status:colour=Yellow|title=X} carries its own unescaped
    | as part of its syntax, not a cell delimiter - protect it first."""
    macros = []

    def protect(m):
        macros.append(m.group(0))
        return f"\x00{len(macros) - 1}\x00"

    row = MACRO_RE.sub(protect, row.strip())

    if row.startswith("||"):
        row = row[2:]
        if row.endswith("||"):
            row = row[:-2]
        sep = "||"
    else:
        row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        sep = "|"
    parts = re.split(r"(?<!\\)\|\|" if sep == "||" else r"(?<!\\)\|", row)

    def restore(cell):
        cell = cell.replace("\\|", "|")
        return re.sub(r"\x00(\d+)\x00", lambda m: macros[int(m.group(1))], cell)

    return [restore(p) for p in parts]


def render_confluence_markup(markup_text):
    lines = markup_text.splitlines()
    out = []
    i = 0
    in_table = False
    table_rows = []

    def flush_table():
        nonlocal in_table, table_rows
        if not table_rows:
            in_table = False
            return
        header, *body = table_rows
        out.append('<div class="table-wrap"><table>')
        out.append("<thead><tr>" + "".join(f"<th>{_render_inline(c)}</th>" for c in header) + "</tr></thead>")
        out.append("<tbody>")
        for row in body:
            out.append("<tr>" + "".join(f"<td>{_render_inline(c)}</td>" for c in row) + "</tr>")
        out.append("</tbody></table></div>")
        table_rows = []
        in_table = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("||"):
            in_table = True
            table_rows.append(_split_cells(stripped))
            i += 1
            continue
        if in_table and stripped.startswith("|"):
            table_rows.append(_split_cells(stripped))
            i += 1
            continue
        if in_table:
            flush_table()

        if not stripped:
            i += 1
            continue
        if stripped == "----":
            out.append("<hr>")
            i += 1
            continue
        if stripped.startswith("h1. "):
            out.append(f"<h1>{_render_inline(stripped[4:])}</h1>")
            i += 1
            continue
        if stripped.startswith("h2. "):
            out.append(f"<h2>{_render_inline(stripped[4:])}</h2>")
            i += 1
            continue

        m = INFO_RE.match(stripped)
        if m:
            out.append(f'<div class="panel info"><b>{_esc(m.group(1))}</b><p>{_render_inline(m.group(2))}</p></div>')
            i += 1
            continue
        m = NOTE_RE.match(stripped)
        if m:
            out.append(f'<div class="panel note"><b>{_esc(m.group(1))}</b><p>{_render_inline(m.group(2))}</p></div>')
            i += 1
            continue

        out.append(f"<p>{_render_inline(stripped)}</p>")
        i += 1

    if in_table:
        flush_table()

    return "\n".join(out)


_PAGE_TEMPLATE = r'''<title>Rule Recovery Wiki Page</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>
  :root{
    --bg:#F5F6F3; --panel:#FFFFFF; --panel-2:#EDEFEA;
    --ink:#1B2430; --ink-soft:#5B6472; --border:rgba(27,36,48,0.12);
    --accent:#0F8F8A; --accent-soft:rgba(15,143,138,0.10);
    --good:#1F8A5F; --good-soft:rgba(31,138,95,0.12);
    --warn:#9A6B12; --warn-soft:rgba(183,121,31,0.14);
    --bad:#B23B3B; --bad-soft:rgba(178,59,59,0.10);
    color-scheme: light;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --bg:#14171A; --panel:#1C2024; --panel-2:#22262B;
      --ink:#E8EAED; --ink-soft:#9AA3AD; --border:rgba(232,234,237,0.14);
      --accent:#3DDAC3; --accent-soft:rgba(61,218,195,0.14);
      --good:#34C185; --good-soft:rgba(52,193,133,0.14);
      --warn:#E0A93E; --warn-soft:rgba(224,169,62,0.16);
      --bad:#E2685F; --bad-soft:rgba(226,104,95,0.14);
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"]{
    --bg:#14171A; --panel:#1C2024; --panel-2:#22262B;
    --ink:#E8EAED; --ink-soft:#9AA3AD; --border:rgba(232,234,237,0.14);
    --accent:#3DDAC3; --accent-soft:rgba(61,218,195,0.14);
    --good:#34C185; --good-soft:rgba(52,193,133,0.14);
    --warn:#E0A93E; --warn-soft:rgba(224,169,62,0.16);
    --bad:#E2685F; --bad-soft:rgba(226,104,95,0.14);
    color-scheme: dark;
  }
  *{box-sizing:border-box;}
  body{background:var(--bg);color:var(--ink);font-family:"Inter",system-ui,-apple-system,sans-serif;padding:28px 16px 64px;}
  .wrap{max-width:840px;margin:0 auto;}
  code,.mono{font-family:"JetBrains Mono",ui-monospace,monospace;}

  .banner{
    display:flex;align-items:center;gap:10px;background:var(--panel-2);border:1px solid var(--border);
    border-radius:10px;padding:11px 14px;margin-bottom:24px;font-size:12.5px;color:var(--ink-soft);
  }
  .banner b{color:var(--ink);}
  .banner .tag{
    font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
    background:var(--warn-soft);color:var(--warn);border-radius:4px;padding:2px 6px;flex-shrink:0;
  }

  .page{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:32px 36px;}
  .page h1{font-family:"Fraunces",Georgia,serif;font-size:27px;font-weight:600;margin:0 0 18px;letter-spacing:-.01em;}
  .page h2{font-family:"Fraunces",Georgia,serif;font-size:19px;font-weight:600;margin:30px 0 10px;letter-spacing:-.005em;}
  .page h2:first-of-type{margin-top:0;}
  .page p{font-size:13.5px;line-height:1.6;color:var(--ink);margin:0 0 10px;}
  .page hr{border:none;border-top:1px solid var(--border);margin:26px 0;}

  .panel{border-radius:8px;padding:12px 16px;margin:0 0 14px;font-size:13px;line-height:1.55;}
  .panel b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px;}
  .panel.info{background:var(--accent-soft);color:var(--ink);}
  .panel.info b{color:var(--accent);}
  .panel.note{background:var(--warn-soft);color:var(--ink);}
  .panel.note b{color:var(--warn);}
  .panel p{margin:0;color:inherit;}

  .table-wrap{overflow-x:auto;margin:0 0 6px;}
  table{width:100%;min-width:640px;table-layout:fixed;border-collapse:collapse;font-size:12.5px;}
  th{
    text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;color:var(--ink-soft);
    border-bottom:2px solid var(--border);padding:7px 10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  }
  td{border-bottom:1px solid var(--border);padding:8px 10px;vertical-align:top;line-height:1.5;word-wrap:break-word;}
  th:nth-child(1), td:nth-child(1){width:8%;font-family:"JetBrains Mono",monospace;font-size:11px;color:var(--accent);}
  th:nth-child(2), td:nth-child(2){width:12%;font-family:"JetBrains Mono",monospace;font-size:11px;}
  th:nth-child(3), td:nth-child(3){width:14%;font-family:"JetBrains Mono",monospace;font-size:10.5px;color:var(--ink-soft);}
  th:nth-child(4), td:nth-child(4){width:46%;}
  th:nth-child(5), td:nth-child(5){width:20%;}

  .lozenge{
    display:inline-block;font-size:10px;font-weight:700;letter-spacing:.02em;text-transform:uppercase;
    border-radius:99px;padding:3px 9px;white-space:nowrap;
  }
  .lozenge.warn{background:var(--warn-soft);color:var(--warn);}
  .lozenge.good{background:var(--good-soft);color:var(--good);}
  .lozenge.bad{background:var(--bad-soft);color:var(--bad);}

  footer{margin-top:24px;font-size:11.5px;color:var(--ink-soft);text-align:center;}
</style>

<div class="wrap">
  <div class="banner">
    <span class="tag">Preview</span>
    <span><b>This is what <code>wiki.py</code> generated</b>, rendered for reading &mdash; not a live Confluence page. There's no Atlassian account connected in this environment to publish it to for real; the Confluence-markup source is in <code>output/wiki_page.confluence</code>, ready to paste into a real page the moment there is one.</span>
  </div>
  <div class="page">
__BODY__
  </div>
  <footer>Rendered from the real Confluence wiki-markup output &middot; CP-04 AI Hackathon</footer>
</div>
'''


def build_preview_html(markup_text):
    body = render_confluence_markup(markup_text)
    return _PAGE_TEMPLATE.replace("__BODY__", body)


def write_preview(path=None, markup_path=None):
    markup_path = Path(markup_path) if markup_path else OUTPUT_DIR / "wiki_page.confluence"
    path = Path(path) if path else OUTPUT_DIR / "wiki_preview.html"
    markup_text = markup_path.read_text()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_preview_html(markup_text))
    return path


if __name__ == "__main__":
    out = write_preview()
    print(f"wrote {out}")
