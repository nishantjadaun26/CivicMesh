"""Explicit live extraction. No fixture reports or automatic paid calls."""

import argparse
import asyncio
from pathlib import Path

from civicmesh_ai.errors import AIError
from civicmesh_ai.providers.gemini import GeminiProvider
from civicmesh_ai.schemas import ExtractionRequest
from pydantic import ValidationError


async def extract_file(path: Path):
    # Bound the read before decoding; UTF-8 takes at most four bytes per character.
    with path.open("rb") as source:
        raw = source.read(40001)
    if len(raw) > 40000:
        raise AIError("invalid_input", "Report file is too large.")
    request = ExtractionRequest(text=raw.decode("utf-8"))
    provider = GeminiProvider.from_environment()
    try:
        result = await provider.extract(request)
        print(result.model_dump_json(indent=2))
    finally:
        await provider.close()


def main():
    parser = argparse.ArgumentParser(description="Run live Gemini extraction on your own report.")
    parser.add_argument("--text-file", required=True, type=Path)
    parser.add_argument("--allow-paid-call", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_call:
        parser.error("This sends report text to Gemini. Pass --allow-paid-call to proceed.")
    try:
        asyncio.run(extract_file(args.text_file))
    except AIError as exc:
        parser.exit(1, f"{exc.code}: {exc}\n")
    except (OSError, UnicodeError):
        parser.exit(1, "Could not read the UTF-8 report file.\n")
    except ValidationError:
        parser.exit(1, "invalid_input: Provide 1 to 10000 characters of report text.\n")


if __name__ == "__main__":
    main()
