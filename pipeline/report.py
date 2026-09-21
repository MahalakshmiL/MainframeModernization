"""
report.py - Two export steps, both deterministic:

  - write_rules_csv: output/rules.json -> output/rules.csv
  - render_dashboard_pdf: renders the dashboard HTML to
    output/Rule-Recovery-Results.pdf via a local Chrome/Chromium's
    headless print-to-pdf. If none is found, this is skipped with a
    clear message rather than failing the whole run - the HTML and
    CSV are still produced either way.
"""

import csv
import shutil
import subprocess
from pathlib import Path

from pipeline.parser import PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "output"

RULES_CSV_FIELDS = ["rule_id", "program", "paragraph", "citation", "rule_text"]

# Common install locations, checked in order, before falling back to PATH
# lookups for chromium/chrome/msedge. Covers the default macOS install path
# (not always on PATH) plus Linux package names.
_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
_CHROME_PATH_NAMES = ["google-chrome", "chromium", "chromium-browser", "msedge"]


def find_chrome():
    for path in _CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    for name in _CHROME_PATH_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def write_rules_csv(rules, path=None):
    path = Path(path) if path else OUTPUT_DIR / "rules.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RULES_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for rule in rules:
            writer.writerow(rule)
    return path


def render_dashboard_pdf(html_path, pdf_path=None, timeout=60):
    html_path = Path(html_path)
    pdf_path = Path(pdf_path) if pdf_path else OUTPUT_DIR / "Rule-Recovery-Results.pdf"
    chrome = find_chrome()
    if not chrome:
        return None, ("No Chrome/Chromium/Edge install found - skipped PDF render. "
                       "Install one of these, or open output/dashboard.html and "
                       "print to PDF manually.")

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome, "--headless", "--disable-gpu", "--no-sandbox",
        f"--print-to-pdf={pdf_path}",
        "--no-pdf-header-footer",
        "--virtual-time-budget=8000",
        f"file://{html_path.resolve()}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"Chrome timed out after {timeout}s rendering the PDF."

    if result.returncode != 0 or not pdf_path.exists():
        stderr_tail = result.stderr.decode(errors="replace")[-400:]
        return None, f"Chrome exited {result.returncode}: {stderr_tail}"
    return pdf_path, None


if __name__ == "__main__":
    import json

    rules = json.loads((OUTPUT_DIR / "rules.json").read_text())
    csv_path = write_rules_csv(rules)
    print(f"wrote {csv_path}")

    from pipeline.dashboard import write_dashboard
    html_path = write_dashboard()
    pdf_path, error = render_dashboard_pdf(html_path)
    if pdf_path:
        print(f"wrote {pdf_path}")
    else:
        print(f"PDF skipped: {error}")
