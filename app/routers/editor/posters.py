# import io

# from fastapi import APIRouter, Depends, HTTPException
# from fastapi.responses import StreamingResponse
# from sqlalchemy.orm import Session

# from ... import models, schemas
# from ...database import get_db
# from ...tiptap_render import build_html

# router = APIRouter(prefix="/public", tags=["public"])


# def _get_public_doc(db: Session, document_id: str) -> models.Document:
#     doc = (
#         db.query(models.Document)
#         .filter(models.Document.id == document_id, models.Document.is_public.is_(True))
#         .first()
#     )
#     if not doc:
#         raise HTTPException(status_code=404, detail="Document introuvable ou non public")
#     return doc


# @router.get("/documents/{document_id}", response_model=schemas.PublicDocumentOut)
# def get_public_document(document_id: str, db: Session = Depends(get_db)):
#     """
#     Accès en lecture seule, sans authentification, à un document explicitement
#     rendu public par son propriétaire (voir PATCH /documents/{id}/public).
#     Ne renvoie aucune information sur le propriétaire ni sur les
#     collaborateurs — uniquement le contenu du document.
#     """
#     return _get_public_doc(db, document_id)


# @router.get("/documents/{document_id}/export/pdf")
# def export_public_pdf(document_id: str, db: Session = Depends(get_db)):
#     """Téléchargement du PDF, sans authentification, pour un document public."""
#     doc = _get_public_doc(db, document_id)

#     try:
#         from weasyprint import HTML
#     except ImportError:
#         raise HTTPException(
#             status_code=501,
#             detail="Export PDF indisponible : installez weasyprint sur le serveur (voir requirements.txt).",
#         )

#     html = build_html(doc.title, doc.content or {})
#     pdf_bytes = HTML(string=html).write_pdf()

#     filename = f"{doc.title[:60].strip() or 'document'}.pdf"
#     return StreamingResponse(
#         io.BytesIO(pdf_bytes),
#         media_type="application/pdf",
#         headers={"Content-Disposition": f'attachment; filename="{filename}"'},
#     )
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ... import models, schemas
from ..auth import get_current_user
from ...database import get_db

router = APIRouter(prefix="/posters", tags=["posters"])


def _get_owned_poster(db: Session, poster_id: str, owner_id: str) -> models.PosterDesign:
    poster = (
        db.query(models.PosterDesign)
        .filter(models.PosterDesign.id == poster_id, models.PosterDesign.owner_id == owner_id)
        .first()
    )
    if not poster:
        raise HTTPException(status_code=404, detail="Affiche introuvable")
    return poster


@router.get("", response_model=List[schemas.PosterOut])
def list_posters(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.PosterDesign)
        .filter(models.PosterDesign.owner_id == current_user.id)
        .order_by(models.PosterDesign.updated_at.desc())
        .all()
    )


@router.post("", response_model=schemas.PosterOut, status_code=201)
def create_poster(
    payload: schemas.PosterCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    poster = models.PosterDesign(
        owner_id=current_user.id,
        title=payload.title or "Affiche sans titre",
        width=payload.width or 800,
        height=payload.height or 1100,
        elements=payload.elements or [],
    )
    db.add(poster)
    db.commit()
    db.refresh(poster)
    return poster


@router.get("/{poster_id}", response_model=schemas.PosterOut)
def get_poster(
    poster_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_poster(db, poster_id, current_user.id)


@router.put("/{poster_id}", response_model=schemas.PosterOut)
def update_poster(
    poster_id: str,
    payload: schemas.PosterUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    poster = _get_owned_poster(db, poster_id, current_user.id)
    if payload.title is not None:
        poster.title = payload.title
    if payload.elements is not None:
        poster.elements = payload.elements
    if payload.thumbnail_url is not None:
        poster.thumbnail_url = payload.thumbnail_url
    db.commit()
    db.refresh(poster)
    return poster


@router.delete("/{poster_id}", status_code=204)
def delete_poster(
    poster_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    poster = _get_owned_poster(db, poster_id, current_user.id)
    db.delete(poster)
    db.commit()
    return None
