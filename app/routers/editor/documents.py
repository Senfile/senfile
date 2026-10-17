from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import models, schemas
from ...access import get_document_with_role, require_owner
from ...auth import get_current_user
from ...database import get_db

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=List[schemas.DocumentOut])
def list_documents(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    owned = (
        db.query(models.Document).filter(models.Document.owner_id == current_user.id).all()
    )
    for d in owned:
        d.role = "owner"

    collaborations = (
        db.query(models.DocumentCollaborator)
        .filter(models.DocumentCollaborator.user_id == current_user.id)
        .all()
    )
    role_by_doc = {c.document_id: c.role for c in collaborations}
    shared_docs = []
    if role_by_doc:
        shared_docs = (
            db.query(models.Document)
            .filter(models.Document.id.in_(role_by_doc.keys()))
            .all()
        )
        for d in shared_docs:
            d.role = role_by_doc.get(d.id, "viewer")

    all_docs = owned + shared_docs
    all_docs.sort(key=lambda d: d.updated_at, reverse=True)
    return all_docs


@router.post("", response_model=schemas.DocumentOut, status_code=201)
def create_document(
    payload: schemas.DocumentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = models.Document(
        owner_id=current_user.id,
        title=payload.title or "Document sans titre",
        content=payload.content or {"type": "doc", "content": [{"type": "paragraph"}]},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    doc.role = "owner"
    return doc


@router.get("/{document_id}", response_model=schemas.DocumentOut)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc, role = get_document_with_role(db, document_id, current_user, "viewer")
    doc.role = role
    return doc


@router.put("/{document_id}", response_model=schemas.DocumentOut)
def update_document(
    document_id: str,
    payload: schemas.DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc, role = get_document_with_role(db, document_id, current_user, "editor")
    if payload.title is not None:
        doc.title = payload.title
    if payload.content is not None:
        doc.content = payload.content
    if payload.thumbnail_url is not None:
        doc.thumbnail_url = payload.thumbnail_url
    db.commit()
    db.refresh(doc)
    doc.role = role
    return doc


@router.post("/{document_id}/duplicate", response_model=schemas.DocumentOut, status_code=201)
def duplicate_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    original, _ = get_document_with_role(db, document_id, current_user, "viewer")
    copy = models.Document(
        owner_id=current_user.id,
        title=f"{original.title} (copie)",
        content=original.content,
        thumbnail_url=original.thumbnail_url,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    copy.role = "owner"
    return copy


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = require_owner(db, document_id, current_user)
    db.delete(doc)
    db.commit()
    return None


@router.patch("/{document_id}/public", response_model=schemas.DocumentOut)
def toggle_public(
    document_id: str,
    payload: schemas.PublicToggle,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = require_owner(db, document_id, current_user)
    doc.is_public = payload.is_public
    db.commit()
    db.refresh(doc)
    doc.role = "owner"
    return doc
