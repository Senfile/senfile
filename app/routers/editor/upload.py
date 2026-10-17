# app/routers/editor/upload.py
import os

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.orm import Session

from ... import models, schemas
from ...auth import get_current_user
from ...config import settings
from ...database import get_db
from ...storage import get_storage
from ...rate_limit import limiter

router = APIRouter(prefix="/upload", tags=["upload"])
ALLOWED_TYPES = {"image/png", "image/jpeg","image/jpg", "image/gif", "image/webp", "image/svg+xml"}
MAX_SIZE_BYTES = 8 * 1024 * 1024  # 8 Mo


@router.post("/image", response_model=schemas.AssetOut, status_code=201)
@limiter.limit(settings.rate_limit_upload)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Format d'image non supporté")

    contents = await file.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Image trop volumineuse (max 8 Mo)")

    ext = os.path.splitext(file.filename or "")[1] or ".png"
    url = get_storage().save(contents, ext)

    asset = models.Asset(
        owner_id=current_user.id,
        filename=file.filename or "image",
        url=url,
        content_type=file.content_type,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
