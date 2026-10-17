import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ... import models, schemas
from ...database import get_db
# from ...tiptap_render import build_html
from ...html_builder import build_pdf   # même générateur que l'export privé

router = APIRouter(prefix="/public", tags=["public"])


def _get_public_doc(db: Session, document_id: str) -> models.Document:
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.is_public.is_(True))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable ou non public")
    return doc


@router.get("/documents/{document_id}", response_model=schemas.PublicDocumentOut)
def get_public_document(document_id: str, db: Session = Depends(get_db)):
    """
    Accès en lecture seule, sans authentification, à un document explicitement
    rendu public par son propriétaire (voir PATCH /documents/{id}/public).
    Ne renvoie aucune information sur le propriétaire ni sur les
    collaborateurs — uniquement le contenu du document.
    """
    return _get_public_doc(db, document_id)


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
@router.get("/documents/{document_id}/export/pdf")
def export_public_pdf(document_id: str, request: Request, db: Session = Depends(get_db)):
    """Téléchargement du PDF, sans authentification, pour un document public."""
    doc = _get_public_doc(db, document_id)

    try:
        pdf_bytes = build_pdf(doc.title, doc.content or {}, base_url=str(request.base_url))
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Export PDF indisponible : installez weasyprint et pypdf sur le serveur.",
        )

    filename = f"{doc.title[:60].strip() or 'document'}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )