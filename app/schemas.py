from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, ConfigDict


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    name: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DocumentCreate(BaseModel):
    title: Optional[str] = "Document sans titre"
    content: Optional[dict] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[dict] = None
    thumbnail_url: Optional[str] = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    content: Any
    thumbnail_url: Optional[str] = None
    is_public: bool = False
    created_at: datetime
    updated_at: datetime
    role: Optional[str] = None  # "owner" | "editor" | "viewer" pour l'utilisateur courant


class PublicToggle(BaseModel):
    is_public: bool


class PublicDocumentOut(BaseModel):
    """Version allégée exposée publiquement : pas d'infos sur le propriétaire."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    content: Any
    updated_at: datetime


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    url: str
    content_type: Optional[str] = None
    created_at: datetime


# --- Partage ---

class InviteCreate(BaseModel):
    email: Optional[EmailStr] = None
    role: str = "editor"  # "viewer" | "editor"


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    token: str
    role: str
    email: Optional[str] = None
    created_at: datetime


class InvitePreview(BaseModel):
    document_title: str
    role: str
    email: Optional[str] = None


class CollaboratorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    user: UserOut


class CollaboratorsResponse(BaseModel):
    collaborators: list[CollaboratorOut]
    pending_invites: list[InviteOut]


# --- Commentaires / suggestions ---

class CommentCreate(BaseModel):
    quoted_text: Optional[str] = None
    content: str


class CommentUpdate(BaseModel):
    resolved: bool


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    quoted_text: Optional[str] = None
    content: str
    resolved: bool
    created_at: datetime
    author: UserOut

    @classmethod
    def from_model(cls, comment):
        return cls(
            id=comment.id,
            quoted_text=comment.quoted_text,
            content=comment.content,
            resolved=comment.resolved == "true",
            created_at=comment.created_at,
            author=UserOut.model_validate(comment.author),
        )


# --- Affiches (canvas libre) ---

class PosterCreate(BaseModel):
    title: Optional[str] = "Affiche sans titre"
    width: Optional[int] = 800
    height: Optional[int] = 1100
    elements: Optional[list] = None


class PosterUpdate(BaseModel):
    title: Optional[str] = None
    elements: Optional[list] = None
    thumbnail_url: Optional[str] = None
    background_color: Optional[str] = None


class PosterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    width: int
    height: int
    elements: Any
    background_color: str = "#ffffff"
    thumbnail_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime



