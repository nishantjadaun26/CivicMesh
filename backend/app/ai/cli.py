"""Explicit live extraction. No fixture reports or automatic paid calls."""

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from civicmesh_ai.errors import AIError
from civicmesh_ai.media import MediaEvidence, validate_media
from civicmesh_ai.providers.gemini import GeminiProvider
from civicmesh_ai.schemas import ExtractionRequest
from pydantic import ValidationError


async def extract_file(path: Path | None, attachments=()):
    """Read bounded private input only after the CLI's explicit paid-call authorization."""
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
    parser.add_argument("--allow-paid-call", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_call:
        parser.error("This sends report evidence to Gemini. Pass --allow-paid-call to proceed.")
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
