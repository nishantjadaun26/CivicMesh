"""Explicit live extraction and offline configuration checks; no automatic API calls."""

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

from civicmesh_ai.errors import AIError
from civicmesh_ai.media import MediaEvidence, validate_media
from civicmesh_ai.providers.gemini import GeminiProvider
from civicmesh_ai.schemas import ExtractionRequest
from pydantic import ValidationError


async def extract_file(path: Path | None, attachments=()):
    """Read bounded private input only after explicit API-call authorization."""
    text = ""
    if path is not None:
        with path.open("rb") as source:
            raw = source.read(40001)
        if len(raw) > 40000:
            raise AIError("invalid_input", "Report file is too large.")
        text = raw.decode("utf-8")
    media = []
    if len(attachments) > 10:
        raise AIError("invalid_input", "Use at most 10 attachments.")
    for evidence_id, mime_type, filename in attachments:
        with Path(filename).open("rb") as source:
            raw = source.read(20 * 1024 * 1024 + 1)
        media.append(MediaEvidence(evidence_id=UUID(evidence_id), mime_type=mime_type, content=raw))
    ids = [item.evidence_id for item in media]
    media = validate_media(media, ids)
    request = ExtractionRequest(text=text, evidence_ids=ids)
    provider = GeminiProvider.from_environment()
    try:
        result = await provider.extract(request, media=media)
        print(result.model_dump_json(indent=2))
    finally:
        await provider.close()


def main():
    """Run explicit live extraction; missing consent or invalid inputs never call Gemini."""
    parser = argparse.ArgumentParser(description="Run live Gemini extraction on your own report.")
    parser.add_argument("--text-file", type=Path)
    parser.add_argument(
        "--media",
        nargs=3,
        action="append",
        default=[],
        metavar=("EVIDENCE_ID", "MIME_TYPE", "FILE"),
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Check local configuration without reading reports or calling Gemini.",
    )
    parser.add_argument(
        "--allow-api-call",
        action="store_true",
        help="Allow one Gemini extraction request; billing depends on your project and model.",
    )
    parser.add_argument(
        "--allow-paid-call", dest="allow_api_call", action="store_true", help=argparse.SUPPRESS
    )
    args = parser.parse_args()
    if args.check_config:
        key_configured = bool(os.getenv("GEMINI_API_KEY", "").strip())
        model_configured = bool(os.getenv("GEMINI_MODEL", "").strip())
        print(
            json.dumps(
                {
                    "key_configured": key_configured,
                    "model_configured": model_configured,
                    "billing_status": "not_verified",
                    "api_request_made": False,
                },
                indent=2,
            )
        )
        parser.exit(0 if key_configured and model_configured else 1)
    if not args.allow_api_call:
        parser.error("This sends report evidence to Gemini. Pass --allow-api-call to proceed.")
    if args.text_file is None and not args.media:
        parser.error("Provide --text-file or --media.")
    try:
        asyncio.run(extract_file(args.text_file, args.media))
    except AIError as exc:
        parser.exit(1, f"{exc.code}: {exc}\n")
    except (OSError, UnicodeError):
        parser.exit(1, "Could not read the UTF-8 report file.\n")
    except (ValidationError, ValueError):
        parser.exit(1, "invalid_input: Check text length, evidence IDs and media format/size.\n")


if __name__ == "__main__":
    main()
