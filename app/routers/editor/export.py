# import io

# from fastapi import APIRouter, Depends, HTTPException
# from fastapi.responses import StreamingResponse
# from sqlalchemy.orm import Session

# from ... import models
# from ...access import get_document_with_role
# from ...auth import get_current_user
# from ...database import get_db
# # from ..tiptap_render import build_html
# from ...html_builder import build_html

# router = APIRouter(prefix="/documents", tags=["export"])


# @router.get("/{document_id}/export/pdf")
# def export_pdf(
#     document_id: str,
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(get_current_user),
# ):
#     doc, _ = get_document_with_role(db, document_id, current_user, "viewer")

#     try:
#         from weasyprint import HTML  # import différé : dépendance lourde, non requise en dev
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


import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ... import models
from ...access import get_document_with_role
from ...auth import get_current_user
from ...database import get_db
from ...html_builder import build_pdf

router = APIRouter(prefix="/documents", tags=["export"])


@router.get("/{document_id}/export/pdf")
def export_pdf(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc, _ = get_document_with_role(db, document_id, current_user, "viewer")

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