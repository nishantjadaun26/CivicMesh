"""Uploads preparation endpoint for authenticated private media."""

from typing import Annotated
from uuid import UUID

from backend.app.api.dependencies.auth import get_current_user_id
from backend.app.database.session import get_db
from backend.app.schemas.uploads import UploadPrepareRequest, UploadPrepareResponse
from backend.app.services.storage.media import StorageService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post(
    "/prepare",
    response_model=UploadPrepareResponse,
    summary="Prepare an authorized private media upload",
    description="Validates media MIME type and file size, and allocates an owner-bound evidence storage record.",
)
async def prepare_upload(
    request: UploadPrepareRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadPrepareResponse:
    """Prepare an authorized private upload destination bound to the authenticated citizen."""
    return await StorageService.prepare_upload(
        owner_id=user_id,
        request=request,
        db=db,
    )
