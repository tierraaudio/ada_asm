"""Pluggable storage for archived datasheet PDFs.

`DatasheetStorage` is the seam: a filesystem driver backs local dev + tests
(no Azure needed), an Azure Blob driver backs production (private container,
managed-identity auth, sha256-keyed dedup). See change
`ingest-component-from-mpn` (datasheet-archival).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Protocol


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def blob_path_for(sha256: str) -> str:
    """Content-addressed path — identical PDFs dedupe to one object."""

    return f"datasheets/{sha256}.pdf"


class DatasheetStorage(Protocol):
    """Stores datasheet PDFs content-addressed by sha256."""

    async def exists(self, sha256: str) -> bool: ...

    async def store(self, content: bytes, *, content_type: str = "application/pdf") -> str:
        """Persist `content` (idempotent on its sha256). Returns the blob path."""
        ...

    async def read(self, blob_path: str) -> bytes:
        """Return the bytes of a stored object (for serving)."""
        ...


def get_datasheet_storage() -> DatasheetStorage:
    """Select the driver from settings: Azure Blob in prod, filesystem locally."""

    from app.core.config import get_settings

    settings = get_settings()
    if settings.datasheet_storage_account_url:
        return AzureBlobDatasheetStorage(
            settings.datasheet_storage_account_url, settings.datasheet_container
        )
    return FilesystemDatasheetStorage(Path(settings.datasheet_local_root))


class FilesystemDatasheetStorage:
    """Filesystem-backed driver for local dev + tests."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _abs(self, sha256: str) -> Path:
        return self._root / blob_path_for(sha256)

    async def exists(self, sha256: str) -> bool:
        return self._abs(sha256).exists()

    async def store(self, content: bytes, *, content_type: str = "application/pdf") -> str:
        sha = sha256_hex(content)
        path = self._abs(sha)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return blob_path_for(sha)

    async def read(self, blob_path: str) -> bytes:
        return (self._root / blob_path).read_bytes()


class AzureBlobDatasheetStorage:
    """Azure Blob driver for production.

    Auth uses the backend Container App's managed identity via
    `DefaultAzureCredential` (Storage Blob Data role) — never an account
    key or connection string. The container is private; serving happens
    through the backend (stream or short user-delegation SAS).
    """

    def __init__(self, account_url: str, container: str) -> None:
        self._account_url = account_url
        self._container = container
        self._client = None  # lazy: avoid importing azure SDK in local/tests

    def _container_client(self) -> Any:
        if self._client is None:
            from azure.identity.aio import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            credential = DefaultAzureCredential()
            service = BlobServiceClient(self._account_url, credential=credential)
            self._client = service.get_container_client(self._container)
        return self._client

    async def exists(self, sha256: str) -> bool:
        blob = self._container_client().get_blob_client(blob_path_for(sha256))
        return bool(await blob.exists())

    async def read(self, blob_path: str) -> bytes:
        blob = self._container_client().get_blob_client(blob_path)
        stream = await blob.download_blob()
        return bytes(await stream.readall())

    async def store(self, content: bytes, *, content_type: str = "application/pdf") -> str:
        import contextlib

        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import ContentSettings

        sha = sha256_hex(content)
        path = blob_path_for(sha)
        blob = self._container_client().get_blob_client(path)
        # Dedup by content hash — a second upload of identical bytes is a no-op.
        with contextlib.suppress(ResourceExistsError):
            await blob.upload_blob(
                content,
                overwrite=False,
                content_settings=ContentSettings(content_type=content_type),
            )
        return path
