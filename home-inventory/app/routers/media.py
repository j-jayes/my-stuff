from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.auth import require_session
from app.deps import get_storage
from app.storage import MediaStorage, ObjectNotFound

router = APIRouter(prefix="/api/media", tags=["media"], dependencies=[Depends(require_session)])


@router.get("/{key:path}")
def get_media(key: str, storage: MediaStorage = Depends(get_storage)) -> StreamingResponse:
    """Serve a stored image behind the session cookie (FR-024).

    Streamed rather than read into memory: Cloud Run caps a buffered response at 32 MiB, and a
    full-size phone photo has no business sitting in the instance's memory on its way out.
    """
    try:
        stream, content_type, size = storage.open(key)
    except ObjectNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such image")

    return StreamingResponse(
        stream,
        media_type=content_type,
        headers={
            # Object keys are immutable, so this can be cached hard and privately.
            "Cache-Control": "private, max-age=31536000, immutable",
            "Content-Length": str(size),
        },
    )
