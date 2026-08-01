"""Wrap private S3-compatible object operations behind normalized errors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from researchmate_api.config import Settings


class ObjectStorageConfigurationError(RuntimeError):
    """Signal incomplete object-storage configuration."""


class ObjectStorageRequestError(RuntimeError):
    """Normalize an object-storage operation failure and retryability."""
    def __init__(self, operation: str, *, retryable: bool) -> None:
        """Capture the failed storage operation and retry classification."""
        super().__init__(f"Object storage {operation} failed")
        self.operation = operation
        self.retryable = retryable


class UploadVerificationError(RuntimeError):
    """Expose a stable code for uploaded-object validation failures."""
    def __init__(self, code: str, message: str) -> None:
        """Capture the stable upload-verification code and safe message."""
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StoredObjectMetadata:
    """Normalize object metadata used to verify an upload."""
    size_bytes: int
    content_type: str | None
    etag: str | None
    metadata: dict[str, str]


class S3CompatibleObjectStorage:
    """Private S3-compatible adapter; provider SDK objects never escape this boundary."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        """Bind verified object-storage settings and an optional injected client."""
        if not settings.object_storage_configured:
            raise ObjectStorageConfigurationError("S3-compatible object storage is not fully configured")
        endpoint_url = settings.object_storage_endpoint_url_resolved
        access_key_id = settings.object_storage_access_key_id_resolved
        secret_access_key = settings.object_storage_secret_access_key_resolved
        bucket = settings.object_storage_bucket_resolved
        if not endpoint_url or not access_key_id or not secret_access_key or not bucket:
            raise ObjectStorageConfigurationError("S3-compatible object storage is not fully configured")
        self.bucket = bucket
        if client is None:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=settings.object_storage_region,
                aws_access_key_id=access_key_id.get_secret_value(),
                aws_secret_access_key=secret_access_key.get_secret_value(),
            )
        self.client = client

    def presign_upload(
        self,
        object_key: str,
        *,
        content_type: str,
        expires_in_seconds: int = 600,
    ) -> str:
        """Create a bounded signed PUT URL for a private object key."""
        try:
            return str(
                self.client.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": self.bucket,
                        "Key": object_key,
                        "ContentType": content_type,
                    },
                    ExpiresIn=expires_in_seconds,
                    HttpMethod="PUT",
                )
            )
        except Exception as exc:
            raise self._normalize_error("presign", exc) from exc

    def head(self, object_key: str) -> StoredObjectMetadata:
        """Read normalized metadata for a private object."""
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=object_key)
        except Exception as exc:
            raise self._normalize_error("head", exc) from exc
        return StoredObjectMetadata(
            size_bytes=int(response["ContentLength"]),
            content_type=response.get("ContentType"),
            etag=str(response["ETag"]).strip('"') if response.get("ETag") else None,
            metadata={str(key): str(value) for key, value in response.get("Metadata", {}).items()},
        )

    def delete(self, object_key: str) -> None:
        """Delete one private object while normalizing provider failures."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=object_key)
        except Exception as exc:
            raise self._normalize_error("delete", exc) from exc

    def download_to_file(self, object_key: str, destination: Path) -> None:
        """Download a private object to a worker-owned path without exposing SDK responses."""
        try:
            with destination.open("wb") as target:
                self.client.download_fileobj(self.bucket, object_key, target)
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise self._normalize_error("download", exc) from exc

    @staticmethod
    def _normalize_error(operation: str, exc: Exception) -> ObjectStorageRequestError:
        """Convert provider exceptions into stable retryable storage failures."""
        response = getattr(exc, "response", None)
        status = None
        if isinstance(response, dict):
            metadata = response.get("ResponseMetadata")
            if isinstance(metadata, dict):
                status = metadata.get("HTTPStatusCode")
        retryable = isinstance(exc, (TimeoutError, ConnectionError)) or status in {
            408,
            409,
            429,
            500,
            502,
            503,
            504,
        }
        return ObjectStorageRequestError(operation, retryable=retryable)


# Retained for existing deployments that still provide the legacy R2_* variables.
R2ObjectStorage = S3CompatibleObjectStorage
