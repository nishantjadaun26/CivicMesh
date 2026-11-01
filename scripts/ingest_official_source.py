"""Owner-reviewed HTML/text source ingestion, with bounded SSRF-safe fetching."""

import argparse
import asyncio
import hashlib
from html.parser import HTMLParser
from pathlib import Path
from uuid import uuid4

from httpx import HTTPError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.errors import AppError
from backend.app.database.models import Authority, SourceChunk, SourceDocument, utc_now
from backend.app.database.session import AsyncSessionLocal
from backend.app.services.routing.official_sources import SafeFetcher


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


async def ingest(arguments):
    if any(not value.strip() or len(value) > 255 for value in (arguments.authority, arguments.jurisdiction, arguments.title)):
        raise ValueError("Authority, jurisdiction and title must contain 1–255 characters")
    if not arguments.verified_official:
        raise ValueError(
            "An owner must verify the domain and passage before using --verified-official"
        )
    passage = " ".join(Path(arguments.passage_file).read_text(encoding="utf-8").split())
    if not 1 <= len(passage) <= 2000:
        raise ValueError("Approved passage must contain 1–2000 characters")
    page = await SafeFetcher.fetch_page(arguments.url)
    parser = Text()
    parser.feed(page)
    page_text = " ".join(" ".join(parser.parts).split())
    if passage not in page_text:
        raise ValueError(
            "The exact approved passage was not found in the fetched document"
        )
    digest = hashlib.sha256(page.encode("utf-8")).hexdigest()
    async with AsyncSessionLocal() as db:
        authority = (
            await db.execute(
                select(Authority).where(
                    Authority.name == arguments.authority,
                    Authority.jurisdiction == arguments.jurisdiction,
                )
            )
        ).scalar_one_or_none()
        if authority is None:
            authority = Authority(
                id=uuid4(),
                name=arguments.authority,
                jurisdiction=arguments.jurisdiction,
            )
            db.add(authority)
            await db.flush()
        existing = (
            (
                await db.execute(
                    select(SourceDocument).where(
                        SourceDocument.authority_id == authority.id,
                        SourceDocument.url == arguments.url,
                        SourceDocument.sha256_hash == digest,
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            print(
                "This source version is already recorded; inspect its passages before changing it."
            )
            return
        document = SourceDocument(
            id=uuid4(),
            authority_id=authority.id,
            title=arguments.title,
            url=arguments.url,
            sha256_hash=digest,
            retrieved_at=utc_now(),
            verified_at=utc_now(),
        )
        db.add(document)
        db.add(SourceChunk(document_id=document.id, chunk_index=0, content=passage))
        await db.commit()
        print(f"Recorded approved source {document.id}. No complaint was submitted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest one genuinely verified official HTML/text passage; no guessed authority catalog."
    )
    parser.add_argument("--authority", required=True)
    parser.add_argument("--jurisdiction", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--passage-file", required=True)
    parser.add_argument("--verified-official", action="store_true")
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    if not arguments.apply:
        print(
            "Plan only. --apply fetches the verified source and writes to the configured database. No connection made."
        )
    else:
        try:
            asyncio.run(ingest(arguments))
        except (OSError, ValueError, RuntimeError, AppError, SQLAlchemyError, HTTPError) as error:
            print(
                f"Source ingestion failed ({type(error).__name__}); document and connection contents omitted."
            )
            raise SystemExit(1) from None
