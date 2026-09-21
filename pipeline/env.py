"""
env.py - Minimal .env loader, no external dependency.

Reads a KEY=VALUE file at the project root (if present) and populates
os.environ for any key not already set there. Exists so ANTHROPIC_API_KEY
can live in a project-local file you own, instead of requiring write
access to a shell startup file like ~/.zshrc (which is root-owned on
some managed machines).
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def load_dotenv(path=ENV_PATH):
    if not Path(path).exists():
        return
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
