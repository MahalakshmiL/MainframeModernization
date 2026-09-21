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

    return {
        "rules": rules,
        "coverage": coverage,
        "contradictions": contradictions,
        "lineage": lineage,
        "rejections": rejections,
        "dead_paragraphs": dead_paragraphs,
        "paragraph_counts": paragraph_counts,
    }


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
  .cov-fill{height:100%;background:var(--good);border-radius:5px;}
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
</style>

<div class="wrap">
  <p class="eyebrow">CP-04 &middot; Mainframe Knowledge Recovery</p>
  <h1>Rule Recovery Results</h1>
  <p class="lede">
    Live output of the extraction agent's run against all six programs &mdash;
    every number on this page came out of <code>output/*.json</code>, none
    of it is hand-typed. Rules are unreviewed until the SME-confirm pill
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

  var covVals = programs.map(function(p){ return data.coverage[p] ? data.coverage[p].coverage_pct : 0; });
  var avgCov = covVals.length ? (covVals.reduce(function(a,b){return a+b;},0) / covVals.length) : 0;
  document.getElementById('stat-programs').textContent = programs.length;
  document.getElementById('stat-rules').textContent = data.rules.length;
  document.getElementById('stat-coverage').textContent = avgCov.toFixed(0) + '%';
  var deadLeaks = data.rules.filter(function(r){
    var dead = data.dead_paragraphs[r.program] || [];
    return dead.indexOf(r.paragraph) !== -1;
  }).length;
  document.getElementById('stat-deadcode').textContent = deadLeaks;
  var driftCount = (data.contradictions.numeric_contradictions.length
    + data.contradictions.field_relationship_contradictions.length
    + data.contradictions.threshold_drift.length);
  document.getElementById('stat-drift').textContent = driftCount;

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
        '<div class="cov-track"><div class="cov-fill" style="width:' + c.coverage_pct + '%"></div></div>' +
        '<div class="cov-pct">' + c.paragraphs_processed + '/' + c.paragraphs_total + ' &middot; ' + c.coverage_pct.toFixed(0) + '%</div>' +
      '</div>' +
      (dead.length ? '<div class="cov-dead" style="margin-left:122px;">' + dead.length + ' dead paragraph' + (dead.length>1?'s':'') + ' excluded (' + dead.join(', ') + ')</div>' : '');
    covList.appendChild(row);
  });

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
