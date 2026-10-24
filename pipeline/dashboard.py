"""
dashboard.py - Builds a static HTML dashboard over the pipeline's real
output (rules.json, coverage.json, contradictions.json,
lineage_report.json). No LLM involved, no live capabilities - every
number in the page is embedded at build time from output/*.json, so
the page is a snapshot of one run, not a live view.
"""

import json
from pathlib import Path

from pipeline.parser import PROJECT_ROOT, parse_all
from pipeline.flowchart import build_all_flows
from pipeline.genie import build_instructions

OUTPUT_DIR = PROJECT_ROOT / "output"


def build_data_bundle(lineage_field="ACCT-INT-RATE"):
    """Assemble everything the dashboard needs from output/*.json plus a
    fresh structural parse (for paragraph counts / dead-paragraph names)."""

    def load(name, default):
        path = OUTPUT_DIR / name
        return json.loads(path.read_text()) if path.exists() else default

    rules = load("rules.json", [])
    coverage = load("coverage.json", {})
    contradictions = load("contradictions.json", {
        "numeric_contradictions": [], "field_relationship_contradictions": [], "threshold_drift": []
    })
    rejections = load("rejections.json", {})

    lineage_path = OUTPUT_DIR / "lineage_report.json"
    if lineage_path.exists():
        lineage = json.loads(lineage_path.read_text())
    else:
        from pipeline.lineage import answer_impact
        lineage = answer_impact(lineage_field)

    programs = parse_all()
    dead_paragraphs = {name: data["dead"] for name, data in programs.items() if data["dead"]}
    paragraph_counts = {
        name: {"total": len(data["paragraph_order"]), "reachable": len(data["reachable"])}
        for name, data in programs.items()
    }

    bundle = {
        "rules": rules,
        "coverage": coverage,
        "contradictions": contradictions,
        "lineage": lineage,
        "rejections": rejections,
        "dead_paragraphs": dead_paragraphs,
        "paragraph_counts": paragraph_counts,
        "flows": build_all_flows(),
    }
    bundle["genie_instructions"] = build_instructions(bundle)
    return bundle


_HTML_TEMPLATE = r'''<title>Rule Recovery Results</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>
  :root{
    --bg:#F5F6F3;
    --panel:#FFFFFF;
    --panel-2:#EDEFEA;
    --ink:#1B2430;
    --ink-soft:#5B6472;
    --border:rgba(27,36,48,0.12);
    --accent:#0F8F8A;
    --accent-deep:#0A6B67;
    --accent-soft:rgba(15,143,138,0.10);
    --good:#1F8A5F;
    --good-soft:rgba(31,138,95,0.12);
    --warn:#9A6B12;
    --warn-soft:rgba(183,121,31,0.14);
    --bad:#B23B3B;
    --bad-soft:rgba(178,59,59,0.10);
    color-scheme: light;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --bg:#14171A;
      --panel:#1C2024;
      --panel-2:#22262B;
      --ink:#E8EAED;
      --ink-soft:#9AA3AD;
      --border:rgba(232,234,237,0.14);
      --accent:#3DDAC3;
      --accent-deep:#179384;
      --accent-soft:rgba(61,218,195,0.14);
      --good:#34C185;
      --good-soft:rgba(52,193,133,0.14);
      --warn:#E0A93E;
      --warn-soft:rgba(224,169,62,0.16);
      --bad:#E2685F;
      --bad-soft:rgba(226,104,95,0.14);
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"]{
    --bg:#14171A;
    --panel:#1C2024;
    --panel-2:#22262B;
    --ink:#E8EAED;
    --ink-soft:#9AA3AD;
    --border:rgba(232,234,237,0.14);
    --accent:#3DDAC3;
    --accent-deep:#179384;
    --accent-soft:rgba(61,218,195,0.14);
    --good:#34C185;
    --good-soft:rgba(52,193,133,0.14);
    --warn:#E0A93E;
    --warn-soft:rgba(224,169,62,0.16);
    --bad:#E2685F;
    --bad-soft:rgba(226,104,95,0.14);
    color-scheme: dark;
  }

  *{box-sizing:border-box;}
  body{
    background:var(--bg);
    color:var(--ink);
    font-family:"Inter",system-ui,-apple-system,sans-serif;
    padding:28px 16px 64px;
  }
  .wrap{max-width:1080px;margin:0 auto;}

  .eyebrow{
    font-size:11.5px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
    color:var(--accent);margin:0 0 8px;
  }
  h1{
    font-family:"Fraunces",Georgia,serif;
    font-size:clamp(26px,3.6vw,34px);
    font-weight:600;margin:0 0 8px;letter-spacing:-.01em;text-wrap:balance;
  }
  p.lede{
    font-size:14.5px;line-height:1.6;color:var(--ink-soft);max-width:70ch;margin:0 0 24px;
  }
  code, .mono{font-family:"JetBrains Mono",ui-monospace,monospace;}

  .stats{
    display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:28px;
  }
  @media (max-width:720px){ .stats{grid-template-columns:repeat(2,1fr);} }
  .stat{
    background:var(--panel);border:1px solid var(--border);border-radius:10px;
    padding:14px 14px;display:flex;flex-direction:column;gap:4px;
  }
  .stat .n{font-family:"Fraunces",Georgia,serif;font-size:26px;font-weight:600;
    font-variant-numeric:tabular-nums;letter-spacing:-.01em;}
  .stat .n.good{color:var(--good);}
  .stat .n.warn{color:var(--warn);}
  .stat .l{font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.05em;}

  section{margin-bottom:32px;}
  h2{
    font-size:15px;font-weight:700;margin:0 0 4px;letter-spacing:-.005em;
  }
  p.section-note{font-size:13px;color:var(--ink-soft);margin:0 0 14px;line-height:1.5;max-width:72ch;}

  .cov-row{
    display:grid;grid-template-columns:110px 1fr 90px;align-items:center;gap:12px;
    padding:7px 0;
  }
  .cov-row .name{font-size:13px;font-weight:600;}
  .cov-track{height:8px;border-radius:5px;background:var(--panel-2);overflow:hidden;}
  .cov-fill{height:100%;background:var(--good);border-radius:5px;
    transition:width .7s cubic-bezier(.16,1,.3,1);}
  @media (prefers-reduced-motion: reduce){ .cov-fill{transition:none;} }
  .cov-pct{font-size:12.5px;color:var(--ink-soft);text-align:right;font-variant-numeric:tabular-nums;}
  .cov-dead{font-size:11.5px;color:var(--warn);margin-top:2px;}

  .drift-card{
    background:var(--panel);border:1px solid var(--border);border-left:3px solid var(--bad);
    border-radius:8px;padding:14px 16px;margin-bottom:12px;
  }
  .drift-card.field{border-left-color:var(--warn);}
  .drift-tag{
    display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
    color:var(--bad);background:var(--bad-soft);border-radius:5px;padding:2px 7px;margin-bottom:8px;
  }
  .drift-card.field .drift-tag{color:var(--warn);background:var(--warn-soft);}
  .drift-compare{
    display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:8px;
  }
  @media (max-width:640px){ .drift-compare{grid-template-columns:1fr;} }
  .drift-side{background:var(--panel-2);border-radius:7px;padding:10px 12px;}
  .drift-side .src{font-size:10.5px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px;}
  .drift-side .val{font-size:13.5px;font-weight:600;}
  .drift-side .loc{font-size:11.5px;color:var(--ink-soft);margin-top:4px;}
  .drift-text{font-size:13.5px;line-height:1.55;margin:0 0 4px;}

  .lineage-card{
    background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:18px 20px;
  }
  .equiv-chain{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px;}
  .equiv-pill{
    font-size:12.5px;font-weight:600;background:var(--accent-soft);color:var(--accent);
    border-radius:6px;padding:4px 10px;
  }
  .equiv-arrow{color:var(--ink-soft);font-size:13px;}
  .lineage-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:4px;}
  @media (max-width:640px){ .lineage-grid{grid-template-columns:1fr;} }
  .lineage-col .label{font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;}
  .lineage-item{font-size:13px;margin-bottom:4px;}
  .lineage-item .p{color:var(--ink-soft);}
  .lineage-summary{font-size:13.5px;line-height:1.6;color:var(--ink-soft);margin-top:14px;padding-top:14px;border-top:1px solid var(--border);}

  .dead-note{
    background:var(--panel);border:1px solid var(--border);border-left:3px solid var(--good);
    border-radius:8px;padding:12px 16px;font-size:13px;line-height:1.55;
  }
  .dead-note b{color:var(--good);}

  .filter-row{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;}
  .filter-btn{
    font-family:inherit;font-size:12.5px;font-weight:600;padding:6px 12px;border-radius:99px;
    border:1px solid var(--border);background:var(--panel);color:var(--ink-soft);cursor:pointer;
  }
  .filter-btn.active{background:var(--ink);color:var(--bg);border-color:var(--ink);}
  .rule-row{
    display:grid;grid-template-columns:1fr auto;gap:10px;align-items:start;
    padding:11px 0;border-bottom:1px solid var(--border);
  }
  .rule-row:last-child{border-bottom:none;}
  .rule-meta{display:flex;gap:8px;align-items:baseline;margin-bottom:3px;flex-wrap:wrap;}
  .rule-cite{font-size:11.5px;color:var(--accent);}
  .rule-text{font-size:13.5px;line-height:1.5;}
  .pill{
    font-size:10px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;
    background:var(--warn-soft);color:var(--warn);border-radius:5px;padding:3px 7px;white-space:nowrap;
    align-self:start;
  }
  .search-box{
    width:100%;font-family:inherit;font-size:13.5px;padding:9px 12px;border-radius:8px;
    border:1px solid var(--border);background:var(--panel);color:var(--ink);margin-bottom:12px;
  }
  .search-box::placeholder{color:var(--ink-soft);}
  .program-group{margin-bottom:6px;}
  .program-head{
    display:flex;align-items:center;gap:8px;padding:10px 0 6px;
  }
  .program-head .pname{font-size:13.5px;font-weight:700;}
  .program-head .pcount{font-size:11.5px;color:var(--ink-soft);}

  footer{margin-top:36px;padding-top:16px;border-top:1px solid var(--border);
    font-size:11.5px;color:var(--ink-soft);}

  .flow-card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px 20px 14px;}
  svg.flow{width:100%;height:auto;display:block;}
  .flow-box{fill:var(--panel-2);stroke:var(--border);stroke-width:1.2;}
  .flow-box.online{fill:var(--accent-soft);stroke:var(--accent);}
  .flow-box.batch{fill:var(--accent-soft);stroke:var(--accent);}
  .flow-box.store{fill:var(--panel);stroke:var(--ink-soft);stroke-dasharray:0;}
  .flow-box.output{fill:var(--good-soft);stroke:var(--good);}
  .flow-label{font-size:12.5px;font-weight:700;fill:var(--ink);font-family:"Inter",sans-serif;}
  .flow-sub{font-size:9.5px;fill:var(--ink-soft);font-family:"JetBrains Mono",monospace;}
  .flow-group-label{font-size:10px;fill:var(--ink-soft);font-family:"Inter",sans-serif;
    text-transform:uppercase;letter-spacing:.05em;}
  .flow-step{font-size:10px;font-weight:700;fill:var(--bg);font-family:"JetBrains Mono",monospace;}
  .flow-legend{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px;font-size:11.5px;color:var(--ink-soft);}
  .flow-legend span{display:inline-flex;align-items:center;gap:7px;}
  .flow-swatch{width:20px;height:0;border-top:1.6px solid var(--ink-soft);display:inline-block;}
  .flow-swatch.dashed{border-top-style:dashed;}
  .flow-swatch.seq{border-top:2.4px solid var(--accent);}

  .pf-card{
    background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:18px 20px 16px;
    box-shadow:0 1px 2px rgba(0,0,0,0.04), 0 10px 28px -14px rgba(0,0,0,0.22);
  }
  .pf-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;}
  .pf-tab{
    font-family:inherit;font-size:12.5px;font-weight:600;padding:6px 13px;border-radius:99px;
    border:1px solid var(--border);background:var(--panel-2);color:var(--ink-soft);cursor:pointer;
    transition:background .15s ease, color .15s ease, border-color .15s ease, transform .1s ease;
  }
  .pf-tab:hover{transform:translateY(-1px);}
  .pf-tab.active{background:var(--ink);color:var(--bg);border-color:var(--ink);}
  .pf-scroll{overflow-x:auto;border-radius:8px;}
  .pf-canvas-wrap{transition:opacity .18s ease;}
  .pf-canvas-wrap.pf-fading{opacity:0;}
  svg.pf-svg{display:block;}
  .pf-edge{
    fill:none;stroke:var(--ink-soft);stroke-width:1.3;opacity:0.55;
    transition:stroke .15s ease, opacity .15s ease, stroke-width .15s ease;
  }
  .pf-edge.pf-lit{stroke:var(--accent);opacity:1;stroke-width:2.1;}
  .pf-edge.pf-dim{opacity:0.14;}
  .pf-node{
    fill:var(--panel-2);stroke:var(--ink-soft);stroke-width:1.1;cursor:default;
    transition:stroke .15s ease, stroke-width .15s ease, fill .15s ease, filter .15s ease;
  }
  .pf-node.entry{fill:var(--accent-soft);stroke:var(--accent);stroke-width:1.7;}
  .pf-node.dead{fill:none;stroke:var(--ink-soft);stroke-width:1;stroke-dasharray:4 3;opacity:0.6;}
  .pf-node.pf-lit{stroke:var(--accent);stroke-width:2.2;filter:drop-shadow(0 2px 6px var(--accent-soft));}
  .pf-node.pf-dim{opacity:0.35;}
  .pf-hit{fill:transparent;cursor:pointer;}
  .pf-label{font-size:10.5px;font-weight:600;fill:var(--ink);font-family:"JetBrains Mono",monospace;
    pointer-events:none;}
  .pf-label.dead{opacity:0.6;}
  .pf-entry-badge{font-size:8.5px;font-weight:700;fill:var(--accent);font-family:"Inter",sans-serif;
    text-transform:uppercase;letter-spacing:.06em;pointer-events:none;}
  .pf-dead-tag{font-size:10px;fill:var(--ink-soft);font-family:"Inter",sans-serif;
    text-transform:uppercase;letter-spacing:.05em;}
  .pf-meta{font-size:12px;color:var(--ink-soft);margin-top:10px;}

  /* genie assistant */
  .genie-fab{
    position:fixed;right:20px;bottom:20px;z-index:40;
    width:52px;height:52px;border-radius:50%;
    background:linear-gradient(135deg, var(--accent), var(--accent-deep));color:var(--bg);border:none;cursor:pointer;
    display:flex;align-items:center;justify-content:center;
    box-shadow:0 2px 6px rgba(0,0,0,0.12), 0 10px 24px -8px rgba(0,0,0,0.3);
    animation:genie-in .4s cubic-bezier(.16,1,.3,1) both;
    transition:transform .15s ease, box-shadow .15s ease;
  }
  .genie-fab:hover{transform:translateY(-2px);box-shadow:0 4px 10px rgba(0,0,0,0.16), 0 14px 30px -8px rgba(0,0,0,0.36);}
  .genie-fab .dot{
    position:absolute;top:4px;right:4px;width:9px;height:9px;border-radius:50%;
    background:var(--good);border:2px solid var(--bg);
  }
  @keyframes genie-in{from{opacity:0;transform:scale(.6);}to{opacity:1;transform:scale(1);}}
  @media (prefers-reduced-motion: reduce){ .genie-fab{animation:none;} }
  .genie-fab[hidden]{display:none;}

  .genie-panel{
    position:fixed;right:20px;bottom:84px;z-index:41;
    width:380px;max-width:calc(100vw - 32px);height:min(560px, calc(100vh - 140px));
    background:var(--panel);border:1px solid var(--border);border-radius:16px;
    box-shadow:0 4px 12px rgba(0,0,0,0.1), 0 24px 56px -16px rgba(0,0,0,0.4);
    display:flex;flex-direction:column;overflow:hidden;
    opacity:0;transform:translateY(10px) scale(.98);pointer-events:none;
    transition:opacity .18s ease, transform .18s cubic-bezier(.16,1,.3,1);
  }
  .genie-panel.open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto;}
  @media (prefers-reduced-motion: reduce){ .genie-panel{transition:none;} }

  .genie-head{
    display:flex;align-items:center;gap:10px;padding:14px 16px;
    border-bottom:1px solid var(--border);background:var(--panel-2);
    flex-shrink:0;
  }
  .genie-head .icon-badge{
    width:30px;height:30px;border-radius:9px;
    background:linear-gradient(135deg, var(--accent), var(--accent-deep));color:var(--bg);
    display:flex;align-items:center;justify-content:center;flex-shrink:0;
  }
  .genie-head .titles{flex:1;min-width:0;}
  .genie-head .t1{font-family:"Fraunces",Georgia,serif;font-size:14px;font-weight:600;line-height:1.2;}
  .genie-head .t2{font-size:10.5px;color:var(--ink-soft);display:flex;align-items:center;gap:5px;}
  .genie-official{
    font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
    background:var(--accent-soft);color:var(--accent);border-radius:4px;padding:1px 5px;
  }
  .genie-close{
    background:none;border:none;color:var(--ink-soft);cursor:pointer;padding:4px;
    border-radius:6px;display:flex;align-items:center;justify-content:center;
  }
  .genie-close:hover{background:var(--border);color:var(--ink);}

  .genie-messages{flex:1;overflow-y:auto;padding:14px 16px;display:flex;flex-direction:column;gap:10px;}
  .genie-row{display:flex;gap:8px;max-width:92%;}
  .genie-row.user{align-self:flex-end;flex-direction:row-reverse;}
  .genie-row.assistant{align-self:flex-start;}
  .genie-avatar{
    width:22px;height:22px;border-radius:7px;flex-shrink:0;margin-top:2px;
    display:flex;align-items:center;justify-content:center;
    background:var(--ink);color:var(--bg);
  }
  .genie-row.user .genie-avatar{background:var(--accent-soft);color:var(--accent);}
  .genie-bubble{
    font-size:13px;line-height:1.5;padding:9px 12px;border-radius:12px;
    white-space:pre-wrap;word-break:break-word;
  }
  .genie-row.assistant .genie-bubble{background:var(--panel-2);color:var(--ink);border-bottom-left-radius:4px;}
  .genie-row.user .genie-bubble{background:var(--ink);color:var(--bg);border-bottom-right-radius:4px;}
  .genie-empty{
    margin:auto;text-align:center;color:var(--ink-soft);font-size:12.5px;padding:0 20px;line-height:1.6;
  }
  .genie-empty .icon-badge{
    width:44px;height:44px;border-radius:13px;margin:0 auto 10px;
    background:linear-gradient(135deg, var(--accent), var(--accent-deep));color:var(--bg);
  }
  .genie-suggest{
    display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:12px;
  }
  .genie-chip{
    font-family:inherit;font-size:11px;padding:5px 10px;border-radius:99px;
    border:1px solid var(--border);background:var(--panel);color:var(--ink-soft);cursor:pointer;
  }
  .genie-chip:hover{border-color:var(--accent);color:var(--accent);}

  .genie-status{font-size:11.5px;color:var(--ink-soft);padding:0 16px 6px;display:none;align-items:center;gap:6px;}
  .genie-status.show{display:flex;}
  .genie-dots span{display:inline-block;width:4px;height:4px;border-radius:50%;background:var(--ink-soft);margin-right:2px;animation:genie-blink 1.2s infinite;}
  .genie-dots span:nth-child(2){animation-delay:.2s;}
  .genie-dots span:nth-child(3){animation-delay:.4s;}
  @keyframes genie-blink{0%,80%,100%{opacity:.25;}40%{opacity:1;}}

  .genie-input-row{
    display:flex;gap:8px;padding:12px;border-top:1px solid var(--border);flex-shrink:0;background:var(--panel);
  }
  .genie-input{
    flex:1;font-family:inherit;font-size:13px;padding:9px 12px;border-radius:10px;
    border:1px solid var(--border);background:var(--panel-2);color:var(--ink);resize:none;
    max-height:90px;line-height:1.4;
  }
  .genie-input:focus{outline:none;border-color:var(--accent);}
  .genie-send{
    width:36px;height:36px;border-radius:10px;border:none;background:var(--ink);color:var(--bg);
    display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;
  }
  .genie-send:disabled{opacity:.4;cursor:default;}
  .genie-foot{font-size:9.5px;color:var(--ink-soft);text-align:center;padding:0 0 10px;}
</style>

<div class="wrap">
  <p class="eyebrow">CP-04 &middot; Mainframe Knowledge Recovery</p>
  <h1>Rule Recovery Results</h1>
  <p class="lede">
    Live output of the extraction agent's run &mdash; across both COBOL and PL/I
    programs &mdash; every number on this page came out of <code>output/*.json</code>,
    none of it is hand-typed. Rules are unreviewed until the SME-confirm pill
    below turns green.
  </p>

  <div class="stats">
    <div class="stat"><span class="n" id="stat-programs">-</span><span class="l">Programs</span></div>
    <div class="stat"><span class="n" id="stat-rules">-</span><span class="l">Rules extracted</span></div>
    <div class="stat"><span class="n good" id="stat-coverage">-</span><span class="l">Avg. coverage</span></div>
    <div class="stat"><span class="n good" id="stat-deadcode">-</span><span class="l">Dead-code leaks</span></div>
    <div class="stat"><span class="n warn" id="stat-drift">-</span><span class="l">Drift caught</span></div>
  </div>

  <section>
    <h2>Coverage by program</h2>
    <p class="section-note">Independently verified &mdash; counted from actual <code>get_paragraph_source</code> calls the agent made, not from what it claims.</p>
    <div id="coverage-list"></div>
  </section>

  <section>
    <h2>How the six COBOL programs fit together</h2>
    <p class="section-note">From the actual parsed file-access per program, not a guess &mdash; e.g. <code>STMTGEN</code> opens <code>ACCOUNT-FILE</code> read-only, so its "last-statement-date" update never persists to disk. (The PL/I program, <code>OVRDRAFT</code>, runs independently and isn't part of this shared-file picture &mdash; see its own card in "Inside each program" below.)</p>
    <div class="flow-card">
      <svg class="flow" viewBox="0 0 850 500" role="img"
        aria-label="Flow diagram: the online programs ACCTINQ, DEPOSIT and WITHDRWL run ad hoc in any order against the shared ACCOUNT-FILE and TRANSACTION-FILE VSAM files. The nightly batch chain runs in fixed order per DPBATCH.jcl: ACCTMSTR, then INTCALC, then STMTGEN, also against the same shared files. ACCTMSTR additionally writes a control report; STMTGEN additionally writes statement output. STMTGEN only reads both shared files, it does not write to them.">
        <defs>
          <marker id="fArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="currentColor" fill-opacity="0.55"/>
          </marker>
          <marker id="fArrowAccent" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--accent)"/>
          </marker>
        </defs>

        <text class="flow-group-label" x="30" y="18">Online / ad hoc &mdash; any program, any order</text>
        <text class="flow-group-label" x="30" y="318">Nightly batch &mdash; DPBATCH.jcl, fixed order</text>

        <!-- data-access arrows (drawn first, so boxes sit on top) -->
        <g stroke="currentColor" stroke-width="1.1" fill="none">
          <line x1="145" y1="90" x2="255" y2="170" stroke-dasharray="4 4" marker-end="url(#fArrow)"/>
          <line x1="410" y1="90" x2="270" y2="170" marker-end="url(#fArrow)"/>
          <line x1="440" y1="90" x2="580" y2="170" marker-end="url(#fArrow)"/>
          <line x1="690" y1="90" x2="300" y2="170" marker-end="url(#fArrow)"/>
          <line x1="710" y1="90" x2="610" y2="170" marker-end="url(#fArrow)"/>

          <line x1="160" y1="330" x2="270" y2="240" marker-end="url(#fArrow)"/>
          <line x1="175" y1="330" x2="560" y2="240" marker-end="url(#fArrow)"/>
          <line x1="425" y1="330" x2="290" y2="240" marker-end="url(#fArrow)"/>
          <line x1="440" y1="330" x2="595" y2="240" marker-end="url(#fArrow)"/>
          <line x1="690" y1="330" x2="320" y2="240" stroke-dasharray="4 4" marker-end="url(#fArrow)"/>
          <line x1="705" y1="330" x2="625" y2="240" stroke-dasharray="4 4" marker-end="url(#fArrow)"/>

          <line x1="145" y1="390" x2="145" y2="428" marker-end="url(#fArrow)"/>
          <line x1="705" y1="390" x2="705" y2="428" marker-end="url(#fArrow)"/>
        </g>

        <!-- batch sequence arrows (accent, on top) -->
        <g stroke="var(--accent)" stroke-width="2.6" fill="none">
          <line x1="262" y1="360" x2="306" y2="360" marker-end="url(#fArrowAccent)"/>
          <line x1="542" y1="360" x2="586" y2="360" marker-end="url(#fArrowAccent)"/>
        </g>
        <circle cx="187" cy="345" r="9" fill="var(--accent)"/>
        <text class="flow-step" x="187" y="349" text-anchor="middle">2</text>
        <circle cx="467" cy="345" r="9" fill="var(--accent)"/>
        <text class="flow-step" x="467" y="349" text-anchor="middle">3</text>

        <!-- row 1: online programs -->
        <rect class="flow-box online" x="30"  y="30" width="230" height="60" rx="8"/>
        <text class="flow-label" x="145" y="56" text-anchor="middle">ACCTINQ</text>
        <text class="flow-sub" x="145" y="74" text-anchor="middle">read-only</text>
        <rect class="flow-box online" x="310" y="30" width="230" height="60" rx="8"/>
        <text class="flow-label" x="425" y="56" text-anchor="middle">DEPOSIT</text>
        <text class="flow-sub" x="425" y="74" text-anchor="middle">reads + updates</text>
        <rect class="flow-box online" x="590" y="30" width="230" height="60" rx="8"/>
        <text class="flow-label" x="705" y="56" text-anchor="middle">WITHDRWL</text>
        <text class="flow-sub" x="705" y="74" text-anchor="middle">reads + updates</text>

        <!-- row 2: shared VSAM files -->
        <rect class="flow-box store" x="105" y="170" width="300" height="70" rx="8"/>
        <text class="flow-label" x="255" y="200" text-anchor="middle">ACCOUNT-FILE</text>
        <text class="flow-sub" x="255" y="217" text-anchor="middle">VSAM, keyed by ACCT-ID</text>
        <rect class="flow-box store" x="445" y="170" width="300" height="70" rx="8"/>
        <text class="flow-label" x="595" y="200" text-anchor="middle">TRANSACTION-FILE</text>
        <text class="flow-sub" x="595" y="217" text-anchor="middle">VSAM, sequential log</text>

        <!-- row 3: nightly batch chain -->
        <rect class="flow-box batch" x="30"  y="330" width="230" height="60" rx="8"/>
        <text class="flow-label" x="145" y="356" text-anchor="middle">ACCTMSTR</text>
        <text class="flow-sub" x="145" y="374" text-anchor="middle">STEP010 &middot; reads + updates</text>
        <rect class="flow-box batch" x="310" y="330" width="230" height="60" rx="8"/>
        <text class="flow-label" x="425" y="356" text-anchor="middle">INTCALC</text>
        <text class="flow-sub" x="425" y="374" text-anchor="middle">STEP020 &middot; reads + updates</text>
        <rect class="flow-box batch" x="590" y="330" width="230" height="60" rx="8"/>
        <text class="flow-label" x="705" y="356" text-anchor="middle">STMTGEN</text>
        <text class="flow-sub" x="705" y="374" text-anchor="middle">STEP030 &middot; read-only</text>

        <!-- row 4: program-specific outputs -->
        <rect class="flow-box output" x="30"  y="430" width="230" height="50" rx="8"/>
        <text class="flow-label" x="145" y="452" text-anchor="middle" font-size="12">Control Report</text>
        <text class="flow-sub" x="145" y="468" text-anchor="middle">CTLRPT</text>
        <rect class="flow-box output" x="590" y="430" width="230" height="50" rx="8"/>
        <text class="flow-label" x="705" y="452" text-anchor="middle" font-size="12">Statement Output</text>
        <text class="flow-sub" x="705" y="468" text-anchor="middle">STMTOUT</text>
      </svg>
      <div class="flow-legend">
        <span><i class="flow-swatch"></i> reads &amp; updates</span>
        <span><i class="flow-swatch dashed"></i> read-only</span>
        <span><i class="flow-swatch seq"></i> runs next (JCL step order)</span>
      </div>
    </div>
    <p class="section-note" style="margin-top:10px;">Final JCL step (STEP040, not drawn) unloads <code>ACCOUNT-FILE</code> / <code>TRANSACTION-FILE</code> into DB2 as <code>ACCOUNT_MASTER</code> / <code>TRANSACTION_LOG</code>.</p>
  </section>

  <section>
    <h2>Inside each program</h2>
    <p class="section-note">The actual PERFORM graph, auto-laid-out by BFS distance from the entry paragraph &mdash; not hand-drawn. Hover a paragraph to trace what it calls. Dead paragraphs sit in their own row, never wired into the live flow.</p>
    <div class="pf-card">
      <div class="pf-tabs" id="pf-tabs"></div>
      <div class="pf-scroll"><div class="pf-canvas-wrap" id="pf-canvas-wrap"></div></div>
      <div class="pf-meta" id="pf-meta"></div>
    </div>
  </section>

  <section>
    <h2>Contradictions &amp; drift caught</h2>
    <p class="section-note">Two different checks: existing wiki pages diffed against extracted rules, and COBOL comparisons diffed directly against each other across programs.</p>
    <div id="drift-list"></div>
  </section>

  <section>
    <h2>Field lineage spotlight</h2>
    <p class="section-note">The REDEFINES case &mdash; two field names sharing one physical storage slot.</p>
    <div class="lineage-card" id="lineage-card"></div>
  </section>

  <section>
    <h2>Dead code, correctly excluded</h2>
    <p class="section-note">Reachability is computed from the PERFORM graph, not guessed &mdash; these paragraphs exist in source but were never given to the agent.</p>
    <div id="dead-list"></div>
  </section>

  <section>
    <h2>All extracted rules</h2>
    <p class="section-note">Every row carries its exact source citation. None are authoritative until an SME confirms them.</p>
    <input class="search-box" id="search" type="text" placeholder="Search rule text or paragraph name&hellip;">
    <div class="filter-row" id="filter-row"></div>
    <div id="rules-list"></div>
  </section>

  <footer id="footer-note"></footer>
</div>

<button class="genie-fab" id="genie-fab" type="button" aria-label="Ask about this repo" hidden>
  <svg viewBox="0 0 31 22" width="24" height="24" fill="none" aria-hidden="true">
    <path d="M5,19 C5,12 8,9 14,9 C19,9 21,12 21,16 C21,19 18,20 13,20 C8,20 5,20 5,19 Z" fill="currentColor"/>
    <path d="M9,9 C9,7 10.5,6 12.5,6 C14.5,6 16,7 16,9 Z" fill="currentColor"/>
    <circle cx="12.5" cy="5" r="1" fill="currentColor"/>
    <path d="M19,13 C22,11 24,8 25,5 L23,4.3 C22,7 20,10 17,12 Z" fill="currentColor"/>
    <path d="M26,1 L27.1,3.5 L29.6,4.6 L27.1,5.7 L26,8.2 L24.9,5.7 L22.4,4.6 L24.9,3.5 Z" fill="currentColor"/>
  </svg>
  <span class="dot" id="genie-dot" hidden></span>
</button>

<div class="genie-panel" id="genie-panel" role="dialog" aria-label="Repo assistant">
  <div class="genie-head">
    <div class="icon-badge">
      <svg viewBox="0 0 31 22" width="19" height="19" fill="none" aria-hidden="true">
        <path d="M5,19 C5,12 8,9 14,9 C19,9 21,12 21,16 C21,19 18,20 13,20 C8,20 5,20 5,19 Z" fill="currentColor"/>
        <path d="M9,9 C9,7 10.5,6 12.5,6 C14.5,6 16,7 16,9 Z" fill="currentColor"/>
        <circle cx="12.5" cy="5" r="1" fill="currentColor"/>
        <path d="M19,13 C22,11 24,8 25,5 L23,4.3 C22,7 20,10 17,12 Z" fill="currentColor"/>
        <path d="M26,1 L27.1,3.5 L29.6,4.6 L27.1,5.7 L26,8.2 L24.9,5.7 L22.4,4.6 L24.9,3.5 Z" fill="currentColor"/>
      </svg>
    </div>
    <div class="titles">
      <div class="t1">Repo Assistant</div>
      <div class="t2">Rule Recovery Results <span class="genie-official">Claude</span></div>
    </div>
    <button class="genie-close" id="genie-close" type="button" aria-label="Close">
      <svg viewBox="0 0 20 20" width="16" height="16" fill="none"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
    </button>
  </div>
  <div class="genie-messages" id="genie-messages">
    <div class="genie-empty" id="genie-empty">
      <div class="icon-badge" style="display:flex;align-items:center;justify-content:center;">
        <svg viewBox="0 0 31 22" width="26" height="26" fill="none" aria-hidden="true">
          <path d="M5,19 C5,12 8,9 14,9 C19,9 21,12 21,16 C21,19 18,20 13,20 C8,20 5,20 5,19 Z" fill="currentColor"/>
          <path d="M9,9 C9,7 10.5,6 12.5,6 C14.5,6 16,7 16,9 Z" fill="currentColor"/>
          <circle cx="12.5" cy="5" r="1" fill="currentColor"/>
          <path d="M19,13 C22,11 24,8 25,5 L23,4.3 C22,7 20,10 17,12 Z" fill="currentColor"/>
          <path d="M26,1 L27.1,3.5 L29.6,4.6 L27.1,5.7 L26,8.2 L24.9,5.7 L22.4,4.6 L24.9,3.5 Z" fill="currentColor"/>
        </svg>
      </div>
      Ask me anything &mdash; general questions, or about this repo: the COBOL programs, extracted rules, lineage, contradictions, or how the pipeline works.
      <div class="genie-suggest">
        <button class="genie-chip" type="button" data-q="What does the REDEFINES issue mean for ACCT-INT-RATE?">REDEFINES issue?</button>
        <button class="genie-chip" type="button" data-q="Why was the fee-waiver threshold flagged as drift?">Fee-waiver drift?</button>
        <button class="genie-chip" type="button" data-q="Which paragraphs are dead code and why?">Dead code?</button>
      </div>
    </div>
  </div>
  <div class="genie-status" id="genie-status">
    <span class="genie-dots"><span></span><span></span><span></span></span>
    <span id="genie-status-text">Thinking&hellip;</span>
  </div>
  <div class="genie-input-row">
    <textarea class="genie-input" id="genie-input" rows="1" placeholder="Ask a question&hellip;"></textarea>
    <button class="genie-send" id="genie-send" type="button" aria-label="Send">
      <svg viewBox="0 0 20 20" width="16" height="16" fill="none"><path d="M3 10h13M10 4l6 6-6 6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </button>
  </div>
  <div class="genie-foot">Answers are generated by Claude from this page's own data &mdash; verify anything important.</div>
</div>

<script id="pipeline-data" type="application/json">__DATA_JSON__</script>
<script>
(function(){
  try {
    var data = JSON.parse(document.getElementById('pipeline-data').textContent);
  } catch(e) {
    document.getElementById('rules-list').textContent = 'Could not load pipeline data.';
    return;
  }

  var programs = Object.keys(data.paragraph_counts).sort();

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function animateNumber(el, target, opts){
    opts = opts || {};
    var suffix = opts.suffix || '', decimals = opts.decimals || 0;
    if (reduceMotion || !window.requestAnimationFrame) { el.textContent = target.toFixed(decimals) + suffix; return; }
    var startTime = null, duration = opts.duration || 900;
    function step(ts){
      if (!startTime) startTime = ts;
      var p = Math.min((ts - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  var covVals = programs.map(function(p){ return data.coverage[p] ? data.coverage[p].coverage_pct : 0; });
  var avgCov = covVals.length ? (covVals.reduce(function(a,b){return a+b;},0) / covVals.length) : 0;
  animateNumber(document.getElementById('stat-programs'), programs.length, {duration: 500});
  animateNumber(document.getElementById('stat-rules'), data.rules.length, {duration: 900});
  animateNumber(document.getElementById('stat-coverage'), avgCov, {suffix: '%', duration: 900});
  var deadLeaks = data.rules.filter(function(r){
    var dead = data.dead_paragraphs[r.program] || [];
    return dead.indexOf(r.paragraph) !== -1;
  }).length;
  animateNumber(document.getElementById('stat-deadcode'), deadLeaks, {duration: 500});
  var driftCount = (data.contradictions.numeric_contradictions.length
    + data.contradictions.field_relationship_contradictions.length
    + data.contradictions.threshold_drift.length);
  animateNumber(document.getElementById('stat-drift'), driftCount, {duration: 650});

  var rejectionCount = 0;
  Object.keys(data.rejections || {}).forEach(function(p){ rejectionCount += data.rejections[p].length; });
  document.getElementById('footer-note').textContent =
    'Generated from a real run of the pipeline against the CP-04 fixture' +
    (rejectionCount ? ' · ' + rejectionCount + ' self-corrected extraction' + (rejectionCount!==1?'s':'') + ' (rejected, then retried)' : '') +
    ' · not SME-reviewed';

  var covList = document.getElementById('coverage-list');
  programs.forEach(function(p){
    var c = data.coverage[p] || {coverage_pct:0, paragraphs_processed:0, paragraphs_total:0};
    var dead = data.dead_paragraphs[p] || [];
    var row = document.createElement('div');
    row.innerHTML =
      '<div class="cov-row">' +
        '<div class="name">' + p + '</div>' +
        '<div class="cov-track"><div class="cov-fill" data-target="' + c.coverage_pct + '" style="width:' + (reduceMotion ? c.coverage_pct : 0) + '%"></div></div>' +
        '<div class="cov-pct">' + c.paragraphs_processed + '/' + c.paragraphs_total + ' &middot; ' + c.coverage_pct.toFixed(0) + '%</div>' +
      '</div>' +
      (dead.length ? '<div class="cov-dead" style="margin-left:122px;">' + dead.length + ' dead paragraph' + (dead.length>1?'s':'') + ' excluded (' + dead.join(', ') + ')</div>' : '');
    covList.appendChild(row);
  });

  if (!reduceMotion){
    var fills = covList.querySelectorAll('.cov-fill');
    fills.forEach(function(f, i){
      setTimeout(function(){ f.style.width = f.getAttribute('data-target') + '%'; }, 80 + i * 70);
    });
  }

  var driftList = document.getElementById('drift-list');
  data.contradictions.field_relationship_contradictions.forEach(function(c){
    var el = document.createElement('div');
    el.className = 'drift-card field';
    el.innerHTML =
      '<span class="drift-tag">Field relationship &middot; ' + c.page + '</span>' +
      '<p class="drift-text">Page describes <code>' + c.field + '</code> as independent. It physically shares storage with: ' +
        c.actual_equivalence_class.filter(function(f){return f!==c.field;}).map(function(f){return '<code>'+f+'</code>';}).join(', ') + '.</p>' +
      '<div class="drift-compare">' +
        '<div class="drift-side"><div class="src">Page says</div><div class="val">&ldquo;' + c.page_statement.replace(/^[-\s]*/,'').replace(/`/g,'') + '&rdquo;</div></div>' +
        '<div class="drift-side"><div class="src">REDEFINES says</div><div class="val">Same physical bytes, ' + c.actual_equivalence_class.length + ' names</div></div>' +
      '</div>';
    driftList.appendChild(el);
  });
  data.contradictions.threshold_drift.forEach(function(c){
    var el = document.createElement('div');
    el.className = 'drift-card';
    el.innerHTML =
      '<span class="drift-tag">Cross-program threshold drift</span>' +
      '<p class="drift-text">Same field, same literal value, compared with a different operator in two programs\' live code:</p>' +
      '<div class="drift-compare">' +
        '<div class="drift-side"><div class="src">' + c.a.program + '</div><div class="val mono">' + c.field + ' ' + c.a.operator + ' ' + c.value + '</div><div class="loc">' + c.a.paragraph + '</div></div>' +
        '<div class="drift-side"><div class="src">' + c.b.program + '</div><div class="val mono">' + c.field + ' ' + c.b.operator + ' ' + c.value + '</div><div class="loc">' + c.b.paragraph + '</div></div>' +
      '</div>';
    driftList.appendChild(el);
  });
  data.contradictions.numeric_contradictions.forEach(function(c){
    var el = document.createElement('div');
    el.className = 'drift-card';
    el.innerHTML =
      '<span class="drift-tag">Numeric drift &middot; ' + c.page + '</span>' +
      '<div class="drift-compare">' +
        '<div class="drift-side"><div class="src">Page says</div><div class="val">' + c.page_numbers.join(', ') + '</div></div>' +
        '<div class="drift-side"><div class="src">Code says (' + c.matched_rule_id + ')</div><div class="val">' + c.code_numbers.join(', ') + '</div></div>' +
      '</div>';
    driftList.appendChild(el);
  });
  if (driftCount === 0) {
    driftList.innerHTML = '<p class="section-note">No contradictions detected.</p>';
  }

  var lc = data.lineage;
  var lineageHtml = '<div class="equiv-chain">' +
    lc.equivalence_class.map(function(f,i){
      return (i>0 ? '<span class="equiv-arrow">=</span>' : '') + '<span class="equiv-pill mono">' + f + '</span>';
    }).join('') + '</div>' +
    '<div class="lineage-grid">' +
      '<div class="lineage-col"><div class="label">Written by</div>' +
        (lc.live_writers.length ? lc.live_writers.map(function(w){
          return '<div class="lineage-item"><span class="mono">' + w.field + '</span> &larr; <b>' + w.program + '</b> <span class="p">' + w.paragraph + '</span></div>';
        }).join('') : '<div class="lineage-item p">Not written by any reachable paragraph</div>') +
      '</div>' +
      '<div class="lineage-col"><div class="label">Read by</div>' +
        (lc.live_readers.length ? lc.live_readers.map(function(r){
          return '<div class="lineage-item"><span class="mono">' + r.field + '</span> &rarr; <b>' + r.program + '</b> <span class="p">' + r.paragraph + '</span></div>';
        }).join('') : '<div class="lineage-item p">Not read by any reachable paragraph</div>') +
      '</div>' +
    '</div>' +
    '<div class="lineage-grid" style="margin-top:10px;">' +
      '<div class="lineage-col"><div class="label">DB2 mapping</div>' +
        Object.keys(lc.db2_mapping).map(function(f){
          var m = lc.db2_mapping[f];
          return '<div class="lineage-item"><span class="mono">' + f + '</span> &rarr; <span class="mono">' + m.table + '.' + m.column + '</span></div>';
        }).join('') +
      '</div>' +
      '<div class="lineage-col"><div class="label">Excluded (dead code)</div>' +
        (lc.dead_code_touches.length ? lc.dead_code_touches.map(function(d){
          return '<div class="lineage-item"><b>' + d.program + '</b> <span class="p">' + d.paragraph + '</span></div>';
        }).join('') : '<div class="lineage-item p">None</div>') +
      '</div>' +
    '</div>' +
    '<p class="lineage-summary">' + lc.impact_summary + '</p>';
  document.getElementById('lineage-card').innerHTML = lineageHtml;

  var deadList = document.getElementById('dead-list');
  var deadPrograms = Object.keys(data.dead_paragraphs);
  if (deadPrograms.length) {
    deadPrograms.forEach(function(p){
      var el = document.createElement('div');
      el.className = 'dead-note';
      el.innerHTML = '<b>' + data.dead_paragraphs[p].length + ' paragraph(s)</b> in <b>' + p + '</b> never reached from its entry point, so the agent never saw them: ' +
        data.dead_paragraphs[p].map(function(x){return '<code>'+x+'</code>';}).join(', ') + '.';
      deadList.appendChild(el);
    });
  } else {
    deadList.innerHTML = '<p class="section-note">No dead code detected in this fixture.</p>';
  }

  // ---- per-program flowchart (auto-layout from pipeline/flowchart.py) ----
  (function(){
    var pfTabs = document.getElementById('pf-tabs');
    var pfWrap = document.getElementById('pf-canvas-wrap');
    var pfMeta = document.getElementById('pf-meta');
    if (!pfTabs || !data.flows) return;

    var pfNames = Object.keys(data.flows).sort();
    var pfActive = pfNames.indexOf('ACCTMSTR') !== -1 ? 'ACCTMSTR' : pfNames[0];

    function wrapLabel(name, maxChars){
      var parts = name.split('-');
      var lines = [], cur = '';
      for (var i = 0; i < parts.length; i++){
        var piece = parts[i];
        var candidate = cur ? cur + '-' + piece : piece;
        if (candidate.length > maxChars && cur){
          lines.push(cur + '-');
          cur = piece;
        } else {
          cur = candidate;
        }
      }
      if (cur) lines.push(cur);
      if (lines.length > 2) lines = [lines[0], lines.slice(1).join('')];
      return lines;
    }

    function svgEl(tag, attrs){
      var el = document.createElementNS('http://www.w3.org/2000/svg', tag);
      for (var k in attrs) el.setAttribute(k, attrs[k]);
      return el;
    }

    function renderFlow(name){
      var flow = data.flows[name];
      var svg = svgEl('svg', {
        'class': 'pf-svg', viewBox: '0 0 ' + flow.width + ' ' + flow.height,
        width: '100%', height: Math.min(flow.height, 520) + 'px',
        role: 'img', 'aria-label': 'PERFORM flowchart for ' + name
      });

      var byName = {};
      flow.nodes.forEach(function(n){ byName[n.name] = n; });

      var edgeEls = {}, allEdgePaths = [];
      flow.edges.forEach(function(e, idx){
        var a = byName[e.from], b = byName[e.to];
        if (!a || !b) return;
        var x1 = a.x + a.w/2, y1 = a.y + a.h;
        var x2 = b.x + b.w/2, y2 = b.y;
        var dy = Math.max((y2 - y1) / 2, 18);
        var d = 'M ' + x1 + ',' + y1 + ' C ' + x1 + ',' + (y1+dy) + ' ' + x2 + ',' + (y2-dy) + ' ' + x2 + ',' + y2;
        var path = svgEl('path', {'class': 'pf-edge', d: d, 'data-from': e.from, 'data-to': e.to});
        svg.appendChild(path);
        (edgeEls[e.from] = edgeEls[e.from] || []).push(path);
        (edgeEls[e.to] = edgeEls[e.to] || []).push(path);
        allEdgePaths.push({path: path, to: e.to});
      });

      var nodeEls = {};
      flow.nodes.forEach(function(n){
        var g = svgEl('g', {});
        if (!reduceMotion){
          g.style.opacity = '0';
          g.style.transform = 'translateY(8px)';
          g.style.transition = 'opacity .36s ease, transform .36s cubic-bezier(.16,1,.3,1)';
        }
        var cls = 'pf-node' + (n.entry ? ' entry' : '') + (n.dead ? ' dead' : '');
        g.appendChild(svgEl('rect', {'class': cls, x: n.x, y: n.y, width: n.w, height: n.h, rx: 7}));

        if (n.entry){
          var bw = 46, bx = n.x + n.w/2 - bw/2, by = n.y - 15;
          g.appendChild(svgEl('rect', {x: bx, y: by, width: bw, height: 13, rx: 6.5, fill: 'var(--accent)'}));
          var bt = svgEl('text', {'class': 'pf-entry-badge', x: n.x + n.w/2, y: by + 9.5, 'text-anchor': 'middle', fill: 'var(--bg)'});
          bt.textContent = 'ENTRY';
          g.appendChild(bt);
        }

        var lines = wrapLabel(n.name, 16);
        var startY = n.y + n.h/2 - (lines.length - 1) * 6;
        lines.forEach(function(line, i){
          var t = svgEl('text', {
            'class': 'pf-label' + (n.dead ? ' dead' : ''),
            x: n.x + n.w/2, y: startY + i * 12, 'text-anchor': 'middle'
          });
          t.textContent = line;
          g.appendChild(t);
        });

        var hit = svgEl('rect', {'class': 'pf-hit', x: n.x, y: n.y, width: n.w, height: n.h});
        g.appendChild(hit);
        svg.appendChild(g);
        nodeEls[n.name] = {g: g, rect: g.querySelector('.pf-node')};

        hit.addEventListener('mouseenter', function(){
          var connected = {};
          connected[n.name] = true;
          (edgeEls[n.name] || []).forEach(function(p){
            p.classList.add('pf-lit');
            connected[p.getAttribute('data-from')] = true;
            connected[p.getAttribute('data-to')] = true;
          });
          Object.keys(nodeEls).forEach(function(key){
            if (connected[key]) nodeEls[key].rect.classList.add('pf-lit');
            else nodeEls[key].rect.classList.add('pf-dim');
          });
          svg.querySelectorAll('.pf-edge').forEach(function(p){
            if (!p.classList.contains('pf-lit')) p.classList.add('pf-dim');
          });
        });
        hit.addEventListener('mouseleave', function(){
          svg.querySelectorAll('.pf-lit, .pf-dim').forEach(function(el){
            el.classList.remove('pf-lit'); el.classList.remove('pf-dim');
          });
        });
      });

      if (flow.dead_row_y !== null && flow.dead_row_y !== undefined){
        var tag = svgEl('text', {'class': 'pf-dead-tag', x: 24, y: flow.dead_row_y - 10});
        tag.textContent = 'Dead code — never reached';
        svg.appendChild(tag);
      }

      return {svg: svg, nodeEls: nodeEls, edgePaths: allEdgePaths};
    }

    function animateFlowEntrance(built, flow){
      if (reduceMotion) return;
      var ys = [];
      flow.nodes.forEach(function(n){ if (ys.indexOf(n.y) === -1) ys.push(n.y); });
      ys.sort(function(a,b){ return a - b; });
      var rowOf = {};
      flow.nodes.forEach(function(n){ rowOf[n.name] = ys.indexOf(n.y); });

      flow.nodes.forEach(function(n){
        var entry = built.nodeEls[n.name];
        if (!entry) return;
        var delay = 40 + rowOf[n.name] * 110;
        setTimeout(function(){
          entry.g.style.opacity = '1';
          entry.g.style.transform = 'translateY(0)';
        }, delay);
      });

      built.edgePaths.forEach(function(item){
        var len = 0;
        try { len = item.path.getTotalLength(); } catch(e) {}
        item.path.style.strokeDasharray = len;
        item.path.style.strokeDashoffset = len;
        item.path.style.transition = 'stroke-dashoffset .5s cubic-bezier(.16,1,.3,1)';
        var delay = 40 + (rowOf[item.to] || 0) * 110 + 70;
        setTimeout(function(){ item.path.style.strokeDashoffset = '0'; }, delay);
      });
    }

    function renderTabs(){
      pfTabs.innerHTML = '';
      pfNames.forEach(function(name){
        var btn = document.createElement('button');
        btn.className = 'pf-tab' + (name === pfActive ? ' active' : '');
        var dead = (data.dead_paragraphs[name] || []).length;
        btn.textContent = name + (dead ? ' · ' + dead + ' dead' : '');
        btn.addEventListener('click', function(){
          if (name === pfActive) return;
          pfActive = name;
          pfWrap.classList.add('pf-fading');
          setTimeout(function(){ draw(); }, 160);
        });
        pfTabs.appendChild(btn);
      });
    }

    function draw(){
      renderTabs();
      pfWrap.innerHTML = '';
      var flow = data.flows[pfActive];
      var built = renderFlow(pfActive);
      pfWrap.appendChild(built.svg);
      animateFlowEntrance(built, flow);
      pfMeta.textContent = flow.nodes.filter(function(n){return !n.dead;}).length + ' live paragraphs, ' +
        flow.edges.length + ' PERFORM edges' +
        (flow.dead_row_y !== null ? ', ' + flow.nodes.filter(function(n){return n.dead;}).length + ' excluded as dead code' : '') +
        ' · entry: ' + flow.entry;
      pfWrap.classList.remove('pf-fading');
    }

    draw();
  })();

  var filterRow = document.getElementById('filter-row');
  var rulesList = document.getElementById('rules-list');
  var activeProgram = 'All';

  function makeBtn(label){
    var btn = document.createElement('button');
    btn.className = 'filter-btn' + (label === activeProgram ? ' active' : '');
    btn.textContent = label + (label !== 'All' ? ' (' + data.rules.filter(function(r){return r.program===label;}).length + ')' : ' (' + data.rules.length + ')');
    btn.dataset.program = label;
    btn.addEventListener('click', function(){
      activeProgram = label;
      Array.prototype.forEach.call(filterRow.children, function(b){ b.classList.toggle('active', b.dataset.program === label); });
      render();
    });
    return btn;
  }
  filterRow.appendChild(makeBtn('All'));
  programs.forEach(function(p){ filterRow.appendChild(makeBtn(p)); });

  function render(){
    var q = document.getElementById('search').value.trim().toLowerCase();
    rulesList.innerHTML = '';
    var visiblePrograms = activeProgram === 'All' ? programs : [activeProgram];
    visiblePrograms.forEach(function(p){
      var rows = data.rules.filter(function(r){
        if (r.program !== p) return false;
        if (!q) return true;
        return r.rule_text.toLowerCase().indexOf(q) !== -1 || r.paragraph.toLowerCase().indexOf(q) !== -1;
      });
      if (!rows.length) return;
      var group = document.createElement('div');
      group.className = 'program-group';
      var cov = data.coverage[p];
      group.innerHTML = '<div class="program-head"><span class="pname">' + p + '</span><span class="pcount">' +
        rows.length + ' rule' + (rows.length!==1?'s':'') + ' &middot; ' + (cov ? cov.coverage_pct.toFixed(0)+'% coverage' : '') + '</span></div>';
      rows.forEach(function(r){
        var row = document.createElement('div');
        row.className = 'rule-row';
        row.innerHTML =
          '<div>' +
            '<div class="rule-meta"><span class="rule-cite mono">' + r.citation + '</span></div>' +
            '<div class="rule-text">' + r.rule_text + '</div>' +
          '</div>' +
          '<span class="pill">Needs SME confirm</span>';
        group.appendChild(row);
      });
      rulesList.appendChild(group);
    });
    if (!rulesList.children.length) {
      rulesList.innerHTML = '<p class="section-note">No rules match.</p>';
    }
  }
  document.getElementById('search').addEventListener('input', render);
  render();

  // ---- genie repo assistant (sample capability) ----
  (function(){
    var fab = document.getElementById('genie-fab');
    var dot = document.getElementById('genie-dot');
    var panel = document.getElementById('genie-panel');
    var closeBtn = document.getElementById('genie-close');
    var messagesEl = document.getElementById('genie-messages');
    var emptyEl = document.getElementById('genie-empty');
    var statusEl = document.getElementById('genie-status');
    var statusText = document.getElementById('genie-status-text');
    var inputEl = document.getElementById('genie-input');
    var sendBtn = document.getElementById('genie-send');
    if (!fab || !panel) return;

    var sample = null;
    var history = [];
    var busy = false;
    var disabledPermanently = false;

    var INSTRUCTIONS = data.genie_instructions;

    function scrollDown(){ messagesEl.scrollTop = messagesEl.scrollHeight; }

    function addBubble(role, text){
      if (emptyEl) emptyEl.hidden = true;
      var row = document.createElement('div');
      row.className = 'genie-row ' + role;
      var avatar = document.createElement('div');
      avatar.className = 'genie-avatar';
      avatar.innerHTML = role === 'user'
        ? '<svg viewBox="0 0 20 20" width="12" height="12" fill="none"><circle cx="10" cy="7" r="3.2" fill="currentColor"/><path d="M3 17c1.5-4 4.5-6 7-6s5.5 2 7 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
        : '<svg viewBox="0 0 28 28" width="13" height="13" fill="none"><path d="M6 17c0-4 2.5-7 8-7s8 3 8 7-3 5-8 5-8-1-8-5z" fill="currentColor"/></svg>';
      var bubble = document.createElement('div');
      bubble.className = 'genie-bubble';
      bubble.textContent = text;
      row.appendChild(avatar);
      row.appendChild(bubble);
      messagesEl.appendChild(row);
      scrollDown();
      return bubble;
    }

    function setBusy(v){
      busy = v;
      sendBtn.disabled = v || disabledPermanently;
      inputEl.disabled = disabledPermanently;
    }

    function errorMessage(code){
      switch(code){
        case 'not_granted': return "This assistant isn't enabled for your account.";
        case 'sampling_disabled': return "Claude isn't available for this account right now.";
        case 'rate_limited': return "Too many requests right now — try again in a moment.";
        case 'session_expired': return "Your session expired — reopen this page and sign in again.";
        case 'refused': return "That request couldn't be answered — try rephrasing it.";
        case 'empty_completion': return "No answer came back — try asking a more specific question.";
        case 'upstream_error': return "Something went wrong on our end — try again.";
        default: return "Something went wrong — try again.";
      }
    }

    var PERMANENT_HIDE_CODES = {not_granted:1, sampling_disabled:1, not_declared:1, capability_disabled:1, capability_removed:1};

    async function send(text){
      text = (text || '').trim();
      if (!text || busy || disabledPermanently) return;
      addBubble('user', text);
      history.push({role:'user', content:text});
      if (history.length > 12) history.splice(0, history.length - 12);
      inputEl.value = '';
      inputEl.style.height = 'auto';
      setBusy(true);
      statusEl.classList.add('show');
      statusText.textContent = 'Thinking…';

      var bubble = null;
      try {
        var result = await sample([{role:'user', content: INSTRUCTIONS}].concat(history), {
          cache: false,
          onText: function(update){
            statusEl.classList.remove('show');
            if (!bubble) bubble = addBubble('assistant', '');
            bubble.textContent = update.text;
            scrollDown();
          }
        });
        history.push({role:'assistant', content: result.text});
        if (result.truncated && bubble) bubble.textContent += '\n\n[answer cut short]';
      } catch (e) {
        statusEl.classList.remove('show');
        var code = e && e.code;
        if (PERMANENT_HIDE_CODES[code]) {
          disabledPermanently = true;
          if (bubble) { bubble.textContent = errorMessage(code); }
          else { addBubble('assistant', errorMessage(code)); }
          setTimeout(function(){ fab.hidden = true; panel.classList.remove('open'); }, 1800);
        } else if (code === 'cancelled') {
          // no-op
        } else {
          if (bubble && e.text) { bubble.textContent = e.text; }
          addBubble('assistant', errorMessage(code));
        }
      } finally {
        setBusy(false);
      }
    }

    sendBtn.addEventListener('click', function(){ send(inputEl.value); });
    inputEl.addEventListener('keydown', function(ev){
      if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); send(inputEl.value); }
    });
    inputEl.addEventListener('input', function(){
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 90) + 'px';
    });
    document.querySelectorAll('.genie-chip').forEach(function(chip){
      chip.addEventListener('click', function(){ send(chip.getAttribute('data-q')); });
    });

    fab.addEventListener('click', function(){
      panel.classList.toggle('open');
      if (panel.classList.contains('open')) setTimeout(function(){ inputEl.focus(); }, 180);
    });
    closeBtn.addEventListener('click', function(){ panel.classList.remove('open'); });
    document.addEventListener('keydown', function(ev){
      if (ev.key === 'Escape') panel.classList.remove('open');
    });

    (async function init(){
      try {
        sample = (window.claude && typeof window.claude.use === 'function') ? await window.claude.use('sample') : null;
      } catch(e) { sample = null; }
      if (sample) {
        fab.hidden = false;
        if (dot) dot.hidden = false;
      }
    })();
  })();
})();
</script>
'''


def build_dashboard_html(bundle):
    data_json = json.dumps(bundle).replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("__DATA_JSON__", data_json)


def write_dashboard(path=None, lineage_field="ACCT-INT-RATE"):
    path = Path(path) if path else OUTPUT_DIR / "dashboard.html"
    bundle = build_data_bundle(lineage_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_dashboard_html(bundle))
    return path


if __name__ == "__main__":
    out = write_dashboard()
    print(f"wrote {out}")
