from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    get_current_user,
)
from ..config import settings
from ..database import get_db
from ..mailer import send_password_reset_email
from ..rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_register)
def register(request: Request, payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un compte existe déjà avec cet email")

    validate_password_strength(payload.password)

    user = models.User(
        email=payload.email,
        name=payload.name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id})
    return schemas.Token(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/login", response_model=schemas.Token)
@limiter.limit(settings.rate_limit_login)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    token = create_access_token({"sub": user.id})
    return schemas.Token(access_token=token, user=schemas.UserOut.model_validate(user))


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
@limiter.limit(settings.rate_limit_login)
def forgot_password(
    request: Request, payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == payload.email).first()

    if user:
        # Invalide les anciens jetons non utilisés pour éviter d'en accumuler.
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user.id,
            models.PasswordResetToken.used_at.is_(None),
        ).delete()

        reset_token = models.PasswordResetToken(
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.add(reset_token)
        db.commit()
        db.refresh(reset_token)

        reset_url = f"{settings.frontend_url}/reset-password/{reset_token.token}"
        send_password_reset_email(user.email, reset_url)

    # Réponse strictement identique que l'email existe ou non : on ne révèle
    # jamais si une adresse est enregistrée (anti-énumération de comptes).
    return {
        "message": "Si un compte existe avec cet email, un lien de réinitialisation vient d'être envoyé."
    }


@router.post("/reset-password")
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    validate_password_strength(payload.new_password)

    token = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token == payload.token)
        .first()
    )
    if not token or token.used_at is not None or token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Lien de réinitialisation invalide ou expiré")

    user = db.query(models.User).filter(models.User.id == token.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Lien de réinitialisation invalide ou expiré")

    user.hashed_password = hash_password(payload.new_password)
    token.used_at = datetime.utcnow()
    db.commit()

    return {"message": "Votre mot de passe a été mis à jour. Vous pouvez vous connecter."}
