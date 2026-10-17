from fastapi import FastAPI, HTTPException, UploadFile, File
from starlette.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from sqlalchemy import create_engine


from . import models
from .config import settings
from .database import engine
from .rate_limit import limiter
from .routers import auth
from .routers.editor import comments, documents, export, posters, public, sharing, upload
from .routers.sheet import analysis, cells, filters, ops, styles, tables, objects

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Editeur Moderne API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [o.strip() for o in settings.cors_origins.split(",")]

print("CORS settings:", repr(settings.cors_origins))
print("CORS origins:", origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# En production avec stockage S3, ce montage n'est pas utilisé pour les nouveaux
# fichiers (servis directement depuis S3/CDN) mais reste utile en local/Homelab.
if settings.storage_backend == "local":
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(export.router)
app.include_router(sharing.router)
app.include_router(comments.router)
app.include_router(posters.router)
app.include_router(public.router)
app.include_router(upload.router)
for m in (tables, cells, ops, filters, analysis, styles, objects): app.include_router(m.router)



@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}



