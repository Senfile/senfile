import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="owner", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    title = Column(String, default="Document sans titre")
    # Contenu riche stocké en JSON (format compatible TipTap / ProseMirror)
    content = Column(JSON, default=dict)
    thumbnail_url = Column(String, nullable=True)
    # Document public : consultable en lecture seule par n'importe qui via
    # /public/documents/{id}, sans authentification (voir routers/public.py).
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="documents")
    collaborators = relationship(
        "DocumentCollaborator", back_populates="document", cascade="all, delete-orphan"
    )
    comments = relationship("Comment", back_populates="document", cascade="all, delete-orphan")


class DocumentCollaborator(Base):
    """Accès accordé à un utilisateur sur un document (autre que le propriétaire)."""

    __tablename__ = "document_collaborators"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False, default="editor")  # "viewer" | "editor"
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="collaborators")
    user = relationship("User")


class DocumentInvite(Base):
    """
    Invitation en attente : soit ciblée sur un email précis, soit un lien
    générique (email=None) que toute personne connectée peut utiliser pour
    rejoindre le document avec le rôle indiqué.
    """

    __tablename__ = "document_invites"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    role = Column(String, nullable=False, default="editor")  # "viewer" | "editor"
    email = Column(String, nullable=True)  # None = lien ouvert
    created_by_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document")


class Comment(Base):
    """
    Commentaire/suggestion ancré sur une portion de texte du document
    (voir extensions/CommentMark.tsx côté front, qui applique une marque
    `commentId` sur la sélection concernée).
    """

    __tablename__ = "comments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id"), nullable=False)
    author_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    quoted_text = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    resolved = Column(String, default="false")  # "true" | "false" (simple, portable)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="comments")
    author = relationship("User")


class PasswordResetToken(Base):
    """Jeton à usage unique pour la réinitialisation de mot de passe, envoyé par email."""

    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class PosterDesign(Base):
    """
    Composition libre de type affiche : éléments positionnés librement
    (x, y, largeur, hauteur, rotation, z-index) plutôt qu'un flux de texte.
    Le détail des éléments (texte, formes, images) est stocké en JSON côté
    front ; le backend ne fait que persister ce blob.
    """

    __tablename__ = "poster_designs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    title = Column(String, default="Affiche sans titre")
    width = Column(Integer, default=800)
    height = Column(Integer, default=1100)
    elements = Column(JSON, default=list)
    background_color = Column(String, default="#ffffff")
    thumbnail_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    url = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="assets")
