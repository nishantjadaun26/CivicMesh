"""Export OpenAPI contract from the FastAPI application to contracts/openapi.json."""

import json
import sys
from pathlib import Path

# Ensure repository root is on Python path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from backend.app.main import app


def export_openapi():
    schema = app.openapi()
    output_path = repo_root / "contracts" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"OpenAPI schema successfully exported to: {output_path}")


if __name__ == "__main__":
    export_openapi()
