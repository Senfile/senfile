"""
Contrôle d'accès centralisé pour les documents partagés.

Trois rôles : "owner" (propriétaire, tous les droits, seul à pouvoir
supprimer/partager), "editor" (peut lire et modifier), "viewer" (lecture
seule + peut commenter). Utilisé par les routers documents/export/comments.
"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from . import models
from .auth import get_current_user
from .database import get_db

ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}


def get_document_with_role(
    db: Session, document_id: str, user: models.User, min_role: str = "viewer"
) -> tuple[models.Document, str]:
    doc = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")

    if doc.owner_id == user.id:
        role = "owner"
    else:
        collab = (
            db.query(models.DocumentCollaborator)
            .filter(
                models.DocumentCollaborator.document_id == document_id,
                models.DocumentCollaborator.user_id == user.id,
            )
            .first()
        )
        if not collab:
            # On ne révèle pas l'existence du document à qui n'y a pas accès.
            raise HTTPException(status_code=404, detail="Document introuvable")
        role = collab.role

    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        raise HTTPException(status_code=403, detail="Droits insuffisants pour cette action")

    return doc, role


def require_owner(db: Session, document_id: str, user: models.User) -> models.Document:
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.owner_id == user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable ou accès refusé")
    return doc
