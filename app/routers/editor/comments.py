from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ... import models, schemas
from ...access import get_document_with_role
from ...auth import get_current_user
from ...database import get_db

router = APIRouter(prefix="/documents/{document_id}/comments", tags=["comments"])


@router.get("", response_model=List[schemas.CommentOut])
def list_comments(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_document_with_role(db, document_id, current_user, "viewer")
    comments = (
        db.query(models.Comment)
        .filter(models.Comment.document_id == document_id)
        .order_by(models.Comment.created_at.asc())
        .all()
    )
    return [schemas.CommentOut.from_model(c) for c in comments]


@router.post("", response_model=schemas.CommentOut, status_code=201)
def create_comment(
    document_id: str,
    payload: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Un lecteur ("viewer") peut commenter/suggérer sans pouvoir éditer le texte.
    get_document_with_role(db, document_id, current_user, "viewer")
    comment = models.Comment(
        document_id=document_id,
        author_id=current_user.id,
        quoted_text=payload.quoted_text,
        content=payload.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return schemas.CommentOut.from_model(comment)


@router.patch("/{comment_id}", response_model=schemas.CommentOut)
def update_comment(
    document_id: str,
    comment_id: str,
    payload: schemas.CommentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_document_with_role(db, document_id, current_user, "viewer")
    comment = (
        db.query(models.Comment)
        .filter(models.Comment.id == comment_id, models.Comment.document_id == document_id)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Commentaire introuvable")
    comment.resolved = "true" if payload.resolved else "false"
    db.commit()
    db.refresh(comment)
    return schemas.CommentOut.from_model(comment)


@router.delete("/{comment_id}", status_code=204)
def delete_comment(
    document_id: str,
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc, role = get_document_with_role(db, document_id, current_user, "viewer")
    comment = (
        db.query(models.Comment)
        .filter(models.Comment.id == comment_id, models.Comment.document_id == document_id)
        .first()
    )
    if not comment:
        return None
    # Seul l'auteur du commentaire ou le propriétaire du document peut le supprimer.
    if comment.author_id != current_user.id and role != "owner":
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas supprimer ce commentaire")
    db.delete(comment)
    db.commit()
    return None
