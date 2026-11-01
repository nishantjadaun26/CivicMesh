"""Loopback-only browser-test harness. Excluded from the production container."""
# ruff: noqa: E402 -- isolate the database environment before importing the application.

import os

if os.environ.get("ENVIRONMENT") != "test":
    raise RuntimeError("Browser harness requires ENVIRONMENT=test")

import asyncio
import hashlib
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

directory = tempfile.TemporaryDirectory(prefix="civicmesh-browser-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(directory.name, 'app.sqlite').as_posix()}"

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.database.models import Base, Evidence, Profile
from backend.app.database.session import AsyncSessionLocal, engine
from backend.app.main import app
from backend.app.schemas.uploads import UploadPrepareResponse
from backend.app.services.storage.media import StorageService
from backend.app.worker.runner import Worker
from backend.tests.workflow_provider import TestProvider
from civicmesh_ai.checkpoints import sqlite_checkpointer
from civicmesh_ai.media import MediaEvidence
from civicmesh_ai.schemas import Extraction
from fastapi import Request, Response

uploads = {}


async def prepare(owner_id, request, db):
    if await db.get(Profile, owner_id) is None:
        db.add(Profile(id=owner_id))
        await db.flush()
    identifier = uuid4()
    db.add(Evidence(id=identifier, owner_id=owner_id, storage_bucket="civicmesh-evidence",
        storage_path=str(identifier), mime_type=request.content_type, file_size_bytes=request.file_size_bytes))
    await db.commit()
    return UploadPrepareResponse(evidence_id=identifier, storage_path=str(identifier),
        upload_url=f"https://isolated-project.supabase.test/storage/v1/object/upload/sign/civicmesh-evidence/{identifier}?token=isolated-test")


async def verify(item):
    content = uploads.get(item.id)
    if content is None or len(content) != item.file_size_bytes:
        raise ValidationError("Evidence upload is not complete.")
    MediaEvidence(evidence_id=item.id, mime_type=item.mime_type, content=content)
    item.verified, item.sha256_hash = True, hashlib.sha256(content).hexdigest()
    return content


class BrowserProvider(TestProvider):
    async def extract(self, request, *, media=()):
        if "needs-clarification" in request.text and not request.clarifications:
            return Extraction(uncertainties=["An isolated test clarification is required."])
        return await super().extract(request, media=media)


@asynccontextmanager
async def lifespan(application):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    StorageService.prepare_upload = staticmethod(prepare)
    StorageService.verify_uploaded_object = staticmethod(verify)
    async with sqlite_checkpointer(Path(directory.name, "checkpoints.sqlite")) as saver:
        worker = Worker(sessions=AsyncSessionLocal, engine=engine, provider=BrowserProvider(),
                         saver=saver, settings=get_settings())
        async def consume():
            while True:
                await worker.run_once()
                await asyncio.sleep(0.05)
        task = asyncio.create_task(consume())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    await engine.dispose()
    directory.cleanup()


app.router.lifespan_context = lifespan


@app.put("/__test_uploads/{identifier}", include_in_schema=False)
async def test_upload(identifier: UUID, request: Request):
    uploads[identifier] = await request.body()
    return Response(status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)
