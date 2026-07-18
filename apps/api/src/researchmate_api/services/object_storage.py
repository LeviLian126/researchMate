from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from researchmate_api.config import Settings


class ObjectStorageConfigurationError(RuntimeError):
    pass


class ObjectStorageRequestError(RuntimeError):
    def __init__(self, operation: str, *, retryable: bool) -> None:
        super().__init__(f"Object storage {operation} failed")
        self.operation = operation
        self.retryable = retryable


class UploadVerificationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StoredObjectMetadata:
    size_bytes: int
    content_type: str | None
    etag: str | None
    metadata: dict[str, str]


class R2ObjectStorage:
    """Private Cloudflare R2 adapter; SDK objects never escape this boundary."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if not settings.r2_configured or not settings.r2_endpoint_url or not settings.r2_bucket:
            raise ObjectStorageConfigurationError("Cloudflare R2 is not fully configured")
        self.bucket = settings.r2_bucket
        if client is None:
            import boto3

            assert settings.r2_access_key_id is not None
            assert settings.r2_secret_access_key is not None
            client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                region_name="auto",
                aws_access_key_id=settings.r2_access_key_id.get_secret_value(),
                aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
            )
        self.client = client

    def presign_upload(
        self,
        object_key: str,
        *,
        content_type: str,
        expires_in_seconds: int = 600,
    ) -> str:
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
