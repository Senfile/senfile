"""
Abstraction de stockage des fichiers (images uploadées).

En développement / Homelab : stockage sur disque local, servi par FastAPI.
En production cloud (AWS/Azure/GCP) : recommandé de basculer sur S3
(ou équivalent GCS/Azure Blob via un wrapper compatible S3, ex. MinIO/Blob S3 API)
pour ne pas dépendre du disque éphémère des conteneurs.

Bascule via la variable d'environnement STORAGE_BACKEND=local|s3
"""
import os
import uuid
from abc import ABC, abstractmethod

from .config import settings


class StorageBackend(ABC):
    @abstractmethod
    def save(self, content: bytes, extension: str) -> str:
        """Enregistre le fichier et retourne l'URL (relative ou absolue) d'accès."""
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def save(self, content: bytes, extension: str) -> str:
        os.makedirs(settings.upload_dir, exist_ok=True)
        stored_name = f"{uuid.uuid4()}{extension}"
        path = os.path.join(settings.upload_dir, stored_name)
        with open(path, "wb") as f:
            f.write(content)
        return f"/uploads/{stored_name}"


class S3Storage(StorageBackend):
    def __init__(self):
        import boto3  # import différé : évite la dépendance en dev local

        self.client = boto3.client("s3", region_name=settings.s3_region)
        self.bucket = settings.s3_bucket

    def save(self, content: bytes, extension: str) -> str:
        stored_name = f"uploads/{uuid.uuid4()}{extension}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=stored_name,
            Body=content,
            ContentType="application/octet-stream",
            ACL="public-read",
        )
        base = settings.s3_public_base_url or f"https://{self.bucket}.s3.{settings.s3_region}.amazonaws.com"
        return f"{base}/{stored_name}"


def get_storage() -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage()
