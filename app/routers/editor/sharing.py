from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ... import models, schemas
from ...access import require_owner
from ...auth import get_current_user
from ...config import settings
from ...database import get_db
from ...mailer import send_invite_email

router = APIRouter(tags=["sharing"])

VALID_ROLES = ("viewer", "editor")


@router.post(
    "/documents/{document_id}/invites", response_model=schemas.InviteOut, status_code=201
)
def create_invite(
    document_id: str,
    payload: schemas.InviteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Rôle invalide")
    doc = require_owner(db, document_id, current_user)  # seul le propriétaire peut inviter

    invite = models.DocumentInvite(
        document_id=document_id,
        role=payload.role,
        email=payload.email,
        created_by_id=current_user.id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    if payload.email:
        invite_url = f"{settings.frontend_url}/invite/{invite.token}"
        send_invite_email(payload.email, current_user.name, doc.title, invite_url, payload.role)

    return invite


@router.get("/documents/{document_id}/collaborators", response_model=schemas.CollaboratorsResponse)
def list_collaborators(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(db, document_id, current_user)

    collaborators = (
        db.query(models.DocumentCollaborator)
        .filter(models.DocumentCollaborator.document_id == document_id)
        .all()
    )
    invites = (
        db.query(models.DocumentInvite)
        .filter(models.DocumentInvite.document_id == document_id)
        .all()
    )
    return schemas.CollaboratorsResponse(
        collaborators=[schemas.CollaboratorOut.model_validate(c) for c in collaborators],
        pending_invites=[schemas.InviteOut.model_validate(i) for i in invites],
    )


@router.delete("/documents/{document_id}/collaborators/{collaborator_id}", status_code=204)
def revoke_collaborator(
    document_id: str,
    collaborator_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(db, document_id, current_user)
    collab = (
        db.query(models.DocumentCollaborator)
        .filter(
            models.DocumentCollaborator.id == collaborator_id,
            models.DocumentCollaborator.document_id == document_id,
        )
        .first()
    )
    if collab:
        db.delete(collab)
        db.commit()
    return None


@router.delete("/documents/{document_id}/invites/{invite_id}", status_code=204)
def revoke_invite(
    document_id: str,
    invite_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(db, document_id, current_user)
    invite = (
        db.query(models.DocumentInvite)
        .filter(
            models.DocumentInvite.id == invite_id,
            models.DocumentInvite.document_id == document_id,
        )
        .first()
    )
    if invite:
        db.delete(invite)
        db.commit()
    return None


@router.get("/invites/{token}", response_model=schemas.InvitePreview)
def preview_invite(token: str, db: Session = Depends(get_db)):
    invite = db.query(models.DocumentInvite).filter(models.DocumentInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation introuvable ou expirée")
    doc = db.query(models.Document).filter(models.Document.id == invite.document_id).first()
    return schemas.InvitePreview(
        document_title=doc.title if doc else "Document", role=invite.role, email=invite.email
    )


@router.post("/invites/{token}/accept")
def accept_invite(
    token: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite = db.query(models.DocumentInvite).filter(models.DocumentInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation introuvable ou expirée")

    # L'email sur l'invitation est informatif (à qui elle était destinée),
    # pas une barrière stricte : exiger une correspondance exacte bloquait
    # l'accès dès que le destinataire créait son compte avec une adresse
    # légèrement différente (autre casse, faute de frappe, adresse pro vs
    # perso...). Le jeton lui-même (reçu uniquement par email) reste la
    # vraie protection, exactement comme pour un lien de partage classique.

    existing = (
        db.query(models.DocumentCollaborator)
        .filter(
            models.DocumentCollaborator.document_id == invite.document_id,
            models.DocumentCollaborator.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        existing.role = invite.role
    else:
        db.add(
            models.DocumentCollaborator(
                document_id=invite.document_id,
                user_id=current_user.id,
                role=invite.role,
            )
        )
    db.commit()
    return {"document_id": invite.document_id}
