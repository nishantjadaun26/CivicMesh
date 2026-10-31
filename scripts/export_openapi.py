"""Run from backend with its virtual environment. No external services required."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import app

target = Path(__file__).resolve().parents[1] / "contracts/openapi.json"
text = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
if "--check" in sys.argv:
    if not target.exists() or target.read_text(encoding="utf-8") != text:
        raise SystemExit("OpenAPI drift: regenerate contracts/openapi.json")
else:
    target.parent.mkdir(exist_ok=True)
    target.write_text(text, encoding="utf-8")
