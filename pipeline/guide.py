"""
guide.py - A narrative, human-readable explainer page: what this repo
does, and what each program does with its real extracted business
rules. The per-program summaries are hand-written (the source doesn't
change), but every rule, citation and coverage number is pulled live
from output/*.json - same discipline as dashboard.py.
"""

import html
from pathlib import Path

from pipeline.dashboard import build_data_bundle
from pipeline.parser import PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "output"

PROGRAM_ORDER = ["ACCTINQ", "DEPOSIT", "WITHDRWL", "INTCALC", "ACCTMSTR", "STMTGEN", "OVRDRAFT"]

PROGRAM_INFO = {
    "ACCTINQ": {
        "role": "Online / ad hoc",
        "tagline": "Read-only account lookup",
        "summary": (
            "The simplest program in the module. Looks up one account by ID and displays "
            "its balance and status. Never writes to any file."
        ),
    },
    "DEPOSIT": {
        "role": "Online / ad hoc",
        "tagline": "Posts a deposit",
        "summary": (
            "Posts a deposit to an account: rejects deposits to closed accounts, reactivates "
            "dormant ones, applies the monthly maintenance fee waiver at a $500 balance "
            "threshold, and logs the transaction."
        ),
    },
    "WITHDRWL": {
        "role": "Online / ad hoc",
        "tagline": "Posts a withdrawal",
        "summary": (
            "Posts a withdrawal: rejects closed or dormant accounts, enforces a $100 "
            "overdraft cushion, and logs the transaction."
        ),
    },
    "INTCALC": {
        "role": "Nightly batch · STEP020",
        "tagline": "Monthly interest calculation",
        "summary": (
            "Calculates and posts monthly interest for active savings accounts only. "
            "Balances of $10,000 or more earn a bonus rate; smaller balances earn the "
            "account's own stored rate — which physically shares storage with the "
            "checking-account fee code via REDEFINES."
        ),
    },
    "ACCTMSTR": {
        "role": "Nightly batch · STEP010",
        "tagline": "Account maintenance — dormancy, fees, closure",
        "summary": (
            "The largest and most complex program. Marks accounts dormant after 180 days of "
            "inactivity, closes them after 365, assigns checking-account fee codes, applies "
            "the monthly maintenance fee (at a threshold that quietly drifted from DEPOSIT's "
            "version), and produces the batch's control totals. Also contains two legacy "
            "paragraphs that nothing calls anymore."
        ),
    },
    "STMTGEN": {
        "role": "Nightly batch · STEP030",
        "tagline": "Statement generation",
        "summary": (
            "Reads each account and its transactions and writes a printed statement. Opens "
            "both input files read-only, so its own 'refresh the last-activity date' logic "
            "never actually persists to disk."
        ),
    },
    "OVRDRAFT": {
        "role": "Online / ad hoc · PL/I",
        "tagline": "Overdraft protection decision",
        "summary": (
            "A companion subsystem written in PL/I rather than COBOL — real mainframe "
            "estates mix languages like this routinely. Decides whether a withdrawal that "
            "would overdraw an account can be covered by linked overdraft protection: denies "
            "outright if nothing is linked, checks the request against the linked limit, and "
            "waives the fee on the account's first use of the month. Runs independently of "
            "the other six programs — it doesn't share their VSAM files."
        ),
    },
}

SEE_ALSO = [
    ("Rule Recovery Pipeline", "Architecture diagram", "https://claude.ai/artifact/SbAS2PByhBBYmoM7DqB2F4"),
    ("Rule Recovery Results", "Live results dashboard", "https://claude.ai/artifact/6EHFTvsqYwzStQM4YADDKv"),
    ("Repo Genie", "Ask questions about this repo", "https://claude.ai/artifact/6WnmFQGgRuwXk5XEFrPu7L"),
    ("GitHub repo", "Full source", "https://github.com/MahalakshmiL/MainframeModernization"),
]


def _esc(s):
    return html.escape(str(s), quote=True)


def build_guide_html(bundle):
    rules_by_program = {}
    for r in bundle["rules"]:
        rules_by_program.setdefault(r["program"], []).append(r)

    coverage = bundle["coverage"]
    dead_paragraphs = bundle["dead_paragraphs"]
    contradictions = bundle["contradictions"]
    total_rules = len(bundle["rules"])
    total_programs = len(bundle["paragraph_counts"])
    total_dead = sum(len(v) for v in dead_paragraphs.values())
    total_drift = (len(contradictions["numeric_contradictions"])
                   + len(contradictions["field_relationship_contradictions"])
                   + len(contradictions["threshold_drift"]))

    program_sections = []
    for name in PROGRAM_ORDER:
        info = PROGRAM_INFO[name]
        rules = rules_by_program.get(name, [])
        cov = coverage.get(name, {})
        dead = dead_paragraphs.get(name, [])

        rule_items = "\n".join(
            f'<li><span class="cite mono">{_esc(r["citation"])}</span>'
            f'<span class="rtext">{_esc(r["rule_text"])}</span></li>'
            for r in rules
        ) or '<li class="none">No rules extracted yet — run the pipeline with an API key.</li>'

        dead_note = ""
        if dead:
            dead_note = (
                '<p class="dead-note"><b>Excluded as dead code:</b> '
                + ", ".join(f'<code>{_esc(d)}</code>' for d in dead)
                + " — present in source, never reached from the entry point, so never "
                  "handed to the extraction agent.</p>"
            )

        cov_pct = cov.get("coverage_pct")
        cov_line = (
            f'{cov.get("paragraphs_processed", "?")}/{cov.get("paragraphs_total", "?")} '
            f'paragraphs · {cov_pct:.0f}% coverage' if cov_pct is not None else "not yet run"
        )

        program_sections.append(f"""
    <section class="program" id="prog-{name.lower()}">
      <div class="program-head">
        <h2>{name}</h2>
        <span class="role-badge">{_esc(info["role"])}</span>
      </div>
      <p class="tagline">{_esc(info["tagline"])}</p>
      <p class="summary">{_esc(info["summary"])}</p>
      <p class="cov-line">{cov_line} · {len(rules)} rule{"s" if len(rules) != 1 else ""} extracted</p>
      <ul class="rules">
        {rule_items}
      </ul>
      {dead_note}
    </section>""")

    see_also_items = "\n".join(
        f'<a class="see-card" href="{_esc(url)}" target="_blank" rel="noopener">'
        f'<span class="t">{_esc(title)}</span><span class="d">{_esc(desc)}</span></a>'
        for title, desc, url in SEE_ALSO
    )

    return f"""<title>Rule Recovery Guide</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>
  :root{{
    --bg:#F5F6F3; --panel:#FFFFFF; --panel-2:#EDEFEA;
    --ink:#1B2430; --ink-soft:#5B6472; --border:rgba(27,36,48,0.12);
    --accent:#0F8F8A; --accent-deep:#0A6B67; --accent-soft:rgba(15,143,138,0.10);
    --warn:#9A6B12; --warn-soft:rgba(183,121,31,0.14);
    color-scheme: light;
  }}
  @media (prefers-color-scheme: dark){{
    :root:not([data-theme="light"]){{
      --bg:#14171A; --panel:#1C2024; --panel-2:#22262B;
      --ink:#E8EAED; --ink-soft:#9AA3AD; --border:rgba(232,234,237,0.14);
      --accent:#3DDAC3; --accent-deep:#179384; --accent-soft:rgba(61,218,195,0.14);
      --warn:#E0A93E; --warn-soft:rgba(224,169,62,0.16);
      color-scheme: dark;
    }}
  }}
  :root[data-theme="dark"]{{
    --bg:#14171A; --panel:#1C2024; --panel-2:#22262B;
    --ink:#E8EAED; --ink-soft:#9AA3AD; --border:rgba(232,234,237,0.14);
    --accent:#3DDAC3; --accent-deep:#179384; --accent-soft:rgba(61,218,195,0.14);
    --warn:#E0A93E; --warn-soft:rgba(224,169,62,0.16);
    color-scheme: dark;
  }}
  *{{box-sizing:border-box;}}
  body{{background:var(--bg);color:var(--ink);font-family:"Inter",system-ui,-apple-system,sans-serif;padding:32px 16px 64px;}}
  .wrap{{max-width:780px;margin:0 auto;}}
  code,.mono{{font-family:"JetBrains Mono",ui-monospace,monospace;}}

  .eyebrow{{font-size:11.5px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:0 0 10px;}}
  h1{{font-family:"Fraunces",Georgia,serif;font-size:clamp(28px,4vw,38px);font-weight:600;margin:0 0 14px;letter-spacing:-.01em;text-wrap:balance;}}
  p.lede{{font-size:15px;line-height:1.65;color:var(--ink-soft);max-width:68ch;margin:0 0 10px;}}

  .stat-strip{{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0 30px;}}
  .stat{{flex:1 1 110px;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:12px 14px;}}
  .stat .n{{font-family:"Fraunces",Georgia,serif;font-size:22px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--accent);}}
  .stat .l{{font-size:10.5px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.04em;}}

  h2.section-title{{font-family:"Fraunces",Georgia,serif;font-size:20px;font-weight:600;margin:38px 0 6px;letter-spacing:-.005em;}}
  p.section-note{{font-size:13.5px;color:var(--ink-soft);margin:0 0 16px;line-height:1.6;max-width:68ch;}}

  .arch-list{{margin:0 0 4px;padding-left:0;list-style:none;}}
  .arch-list li{{font-size:13.5px;line-height:1.6;padding:8px 0;border-bottom:1px solid var(--border);}}
  .arch-list li:last-child{{border-bottom:none;}}
  .arch-list code{{color:var(--accent);}}

  .program{{
    background:var(--panel);border:1px solid var(--border);border-radius:14px;
    padding:20px 22px;margin-bottom:16px;
  }}
  .program-head{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:2px;}}
  .program h2{{font-family:"JetBrains Mono",monospace;font-size:17px;font-weight:700;margin:0;}}
  .role-badge{{
    font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
    background:var(--accent-soft);color:var(--accent);border-radius:5px;padding:2px 8px;
  }}
  .tagline{{font-size:13.5px;font-weight:600;color:var(--ink);margin:6px 0 4px;}}
  .summary{{font-size:13.5px;line-height:1.6;color:var(--ink-soft);margin:0 0 10px;max-width:64ch;}}
  .cov-line{{font-size:11.5px;color:var(--ink-soft);margin:0 0 10px;font-variant-numeric:tabular-nums;}}
  ul.rules{{list-style:none;margin:0;padding:0;border-top:1px solid var(--border);}}
  ul.rules li{{padding:9px 0;border-bottom:1px solid var(--border);font-size:13px;line-height:1.5;}}
  ul.rules li.none{{color:var(--ink-soft);font-style:italic;}}
  ul.rules .cite{{display:block;font-size:10.5px;color:var(--accent);margin-bottom:2px;}}
  ul.rules .rtext{{color:var(--ink);}}
  .dead-note{{
    margin:12px 0 0;padding:10px 12px;font-size:12px;line-height:1.55;color:var(--warn);
    background:var(--warn-soft);border-radius:8px;
  }}
  .dead-note code{{color:inherit;}}

  .see-also{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;}}
  @media (max-width:540px){{.see-also{{grid-template-columns:1fr;}}}}
  .see-card{{
    display:flex;flex-direction:column;gap:2px;background:var(--panel);border:1px solid var(--border);
    border-radius:10px;padding:12px 14px;text-decoration:none;color:inherit;
  }}
  .see-card:hover{{border-color:var(--accent);}}
  .see-card .t{{font-size:13px;font-weight:600;color:var(--ink);}}
  .see-card .d{{font-size:11.5px;color:var(--ink-soft);}}

  footer{{margin-top:36px;padding-top:16px;border-top:1px solid var(--border);font-size:11.5px;color:var(--ink-soft);}}
</style>

<div class="wrap">
  <p class="eyebrow">CP-04 &middot; Hogan Estate &middot; Deposit / Account Servicing</p>
  <h1>What the mainframe programs do</h1>
  <p class="lede">
    A simplified deposit and account-servicing module: six COBOL programs running on a
    mainframe, from a teller posting a single deposit to the nightly batch run that charges
    fees, closes dormant accounts, and prints statements &mdash; plus a seventh program,
    overdraft protection, written in PL/I rather than COBOL, the way real mainframe estates
    often mix languages by subsystem. What follows is a plain-English account of what each
    program actually does and the business rules inside it &mdash; read from the live code
    paragraph by paragraph, not from documentation that may have gone stale.
  </p>
  <p class="lede">
    Three COBOL programs are <b>online</b>, run ad hoc in any order whenever a transaction
    comes in: <code>ACCTINQ</code>, <code>DEPOSIT</code>, <code>WITHDRWL</code>. Three run as
    a <b>nightly batch</b> in a fixed sequence set by the JCL: <code>ACCTMSTR</code>, then
    <code>INTCALC</code>, then <code>STMTGEN</code>. All six read and write the same two
    shared files &mdash; <code>ACCOUNT-FILE</code> and <code>TRANSACTION-FILE</code> &mdash;
    and the batch's output is unloaded nightly into DB2. <code>OVRDRAFT</code>, the PL/I
    program, runs independently of all six and doesn't touch those files.
  </p>

  <h2 class="section-title">What it accomplishes</h2>
  <p class="section-note">The programs are the mechanism. This is the job they do.</p>
  <ul class="arch-list">
    <li><b>Lets a customer move money</b> &mdash; deposit into or withdraw from their account, with guardrails: a closed account can't be touched, a withdrawal can't push the balance past a $100 overdraft cushion, and a dormant account is automatically reactivated the moment a deposit comes in rather than requiring a separate "unfreeze" step.</li>
    <li><b>Rewards savers, charges accounts that run low</b> &mdash; savings balances earn monthly interest, with a bonus rate once a balance clears $10,000; checking and savings accounts below a minimum balance are charged a monthly maintenance fee instead of earning anything.</li>
    <li><b>Winds down abandoned accounts on its own</b> &mdash; an account with no activity for 180 days is flagged dormant, and after a full year with still no activity it's closed outright, so nobody has to manually notice and act on accounts customers have walked away from.</li>
    <li><b>Backstops honest overdrafts instead of just bouncing them</b> &mdash; the PL/I program decides, per request, whether a withdrawal that would overdraw an account can be covered by linked overdraft protection, waiving the fee on an account's first use each month rather than penalizing an occasional slip-up.</li>
    <li><b>Keeps the customer informed</b> &mdash; a statement is produced for every account, showing the current balance and every transaction behind it.</li>
    <li><b>Feeds the rest of the bank</b> &mdash; account and transaction data is unloaded into DB2 every night, so reporting, compliance, and other downstream systems are working from the same numbers the account-servicing programs just produced.</li>
  </ul>

  <div class="stat-strip">
    <div class="stat"><span class="n">{total_programs}</span><span class="l">Programs</span></div>
    <div class="stat"><span class="n">{total_rules}</span><span class="l">Business rules</span></div>
    <div class="stat"><span class="n">{total_dead}</span><span class="l">Dead paragraphs excluded</span></div>
    <div class="stat"><span class="n">{total_drift}</span><span class="l">Contradictions caught</span></div>
  </div>

  <h2 class="section-title">How the system is organized</h2>
  <p class="section-note">No direct program-to-program calls among the six COBOL programs &mdash; the two shared files are the only thing tying them together. The PL/I program stands apart entirely.</p>
  <ul class="arch-list">
    <li><b>Online, any order</b> &mdash; <code>ACCTINQ</code> (balance lookup, read-only), <code>DEPOSIT</code>, <code>WITHDRWL</code>. Each opens <code>ACCOUNT-FILE</code> by account ID; <code>DEPOSIT</code> and <code>WITHDRWL</code> also update it and append to <code>TRANSACTION-FILE</code>.</li>
    <li><b>Nightly batch, fixed order</b> (<code>DPBATCH.jcl</code>) &mdash; STEP010 <code>ACCTMSTR</code> (dormancy, closure, fee codes, monthly fees, control totals), STEP020 <code>INTCALC</code> (interest), STEP030 <code>STMTGEN</code> (statements). Each step reads <code>ACCOUNT-FILE</code> sequentially, one account after another.</li>
    <li><b>Shared files</b> &mdash; <code>ACCOUNT-FILE</code> (VSAM, keyed by account ID) and <code>TRANSACTION-FILE</code> (VSAM, a sequential log) are the only state the six COBOL programs have in common.</li>
    <li><b>Downstream</b> &mdash; a final batch step unloads both files into DB2 as <code>ACCOUNT_MASTER</code> and <code>TRANSACTION_LOG</code>.</li>
    <li><b>PL/I companion, separate</b> &mdash; <code>OVRDRAFT</code> runs on its own, with its own request/response files, and isn't wired into the COBOL programs' shared state in this fixture.</li>
  </ul>

  <h2 class="section-title">Every program</h2>
  <p class="section-note">Every rule below is pulled live from the extraction agent's real output &mdash; nothing here is hand-typed.</p>
{"".join(program_sections)}

  <h2 class="section-title">Where this came from</h2>
  <p class="section-note">These rules were recovered automatically, each one cited back to its source paragraph, by a small pipeline rather than typed up by hand. The links below go to the pipeline's architecture, its live results, and a way to ask it questions directly.</p>
  <div class="see-also">
{see_also_items}
  </div>

  <footer>Deposit &amp; Account-Servicing System Guide &middot; CP-04 AI Hackathon &middot; generated from the real pipeline output, not a mockup</footer>
</div>
"""


def write_guide(path=None, lineage_field="ACCT-INT-RATE"):
    path = Path(path) if path else OUTPUT_DIR / "guide.html"
    bundle = build_data_bundle(lineage_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_guide_html(bundle))
    return path


if __name__ == "__main__":
    out = write_guide()
    print(f"wrote {out}")
