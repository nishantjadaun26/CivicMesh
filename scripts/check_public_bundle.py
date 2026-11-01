"""Reject server-only identifiers, known fixture secrets, or configured secrets in SPA assets."""

import os
from pathlib import Path

SERVER_VARIABLES = (
    "GEMINI_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET",
    "CHECKPOINT_DATABASE_URL", "DATABASE_URL",
)


def main():
    directory = Path(__file__).resolve().parents[1] / "frontend/dist"
    files = [file for file in directory.rglob("*") if file.suffix in {".js", ".html", ".map"}]
    if not files:
        raise RuntimeError("Build the frontend before checking its assets")
    content = b"\n".join(file.read_bytes() for file in files)
    for name in SERVER_VARIABLES:
        value = os.environ.get(name, "")
        if name.encode() in content or (len(value) >= 16 and value.encode() in content):
            raise RuntimeError(f"Server-only data detected in frontend assets: {name}; value omitted")
    if b"isolated-browser-test-secret-never-used-in-runtime" in content:
        raise RuntimeError("Browser test fixture secret appeared in a production asset")
    print("Public assets contain no checked server-only identifiers, configured secrets or test signing key.")


if __name__ == "__main__":
    main()
