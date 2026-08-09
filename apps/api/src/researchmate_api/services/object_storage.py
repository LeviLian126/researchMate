"""Wrap private S3-compatible object operations behind normalized errors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

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


# Map declared MIME types to the magic-byte signatures that python-magic is expected to
# surface for a genuinely matching file. Values are kept as prefixes so that parameter
# suffixes (e.g. " application/pdf; charset=binary" in some libmagic builds) still match.
_MIME_MAGIC_ALIASES: dict[str, tuple[str, ...]] = {
    "application/pdf": ("application/pdf",),
    "image/png": ("image/png",),
    "image/jpeg": ("image/jpeg", "image/jpg"),
    "image/gif": ("image/gif",),
    "image/webp": ("image/webp",),
    "text/plain": ("text/plain", "ascii"),
    "text/markdown": ("text/plain", "ascii"),
    "text/csv": ("text/plain", "csv", "ascii"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "application/vnd.openxmlformats",
        "application/zip",
    ),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "application/vnd.openxmlformats",
        "application/zip",
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "application/vnd.openxmlformats",
        "application/zip",
    ),
    "application/vnd.ms-powerpoint": ("application/vnd.ms-powerpoint", "application/xzip"),
    "application/vnd.ms-excel": ("application/vnd.ms-excel", "application/xzip"),
    "application/msword": ("application/msword", "application/x-zip-compressed"),
    "application/zip": ("application/zip",),
    "application/json": ("application/json", "text/plain", "ascii"),
}


def _detect_mime_type(data: bytes) -> str | None:
    """Return the libmagic-detected MIME type for the first chunk of bytes.

    The python-magic library is loaded lazily so that environments without it (e.g. worker
    pods that do not upload files) can still import this module. ``None`` is returned when
    the library is unavailable, which callers treat as "skip validation".
    """
    if not data:
        return None
    try:
        import magic
    except ModuleNotFoundError:
        return None
    try:
        return magic.from_buffer(data, mime=True)
    except Exception:  # pragma: no cover - libmagic is a C extension; defensive only.
        return None


def _mime_matches(detected: str | None, declared: str) -> bool:
    """Return True when the detected MIME is a known alias of the declared type."""
    if detected is None:
        # Without libmagic available we cannot verify; fail open to avoid blocking uploads
        # in environments that deliberately skip the optional python-magic dependency.
        return True
    declared_lower = declared.lower()
    aliases = _MIME_MAGIC_ALIASES.get(declared_lower)
    detected_lower = detected.lower()
    if aliases:
        return any(alias in detected_lower for alias in aliases)
    # Unknown-to-the-allowlist declared type: accept when libmagic agrees with the declared
    # type itself (covers rare types not enumerated above).
    return declared_lower in detected_lower or detected_lower.startswith(declared_lower)


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
            raise ObjectStorageConfigurationError(
                "S3-compatible object storage is not fully configured"
            )
        endpoint_url = settings.object_storage_endpoint_url_resolved
        access_key_id = settings.object_storage_access_key_id_resolved
        secret_access_key = settings.object_storage_secret_access_key_resolved
        bucket = settings.object_storage_bucket_resolved
        if not endpoint_url or not access_key_id or not secret_access_key or not bucket:
            raise ObjectStorageConfigurationError(
                "S3-compatible object storage is not fully configured"
            )
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

    def upload_stream(self, object_key: str, source: IO[bytes], *, content_type: str) -> None:
        """Upload a bounded server-received stream without relying on browser S3 CORS."""
        try:
            self.client.upload_fileobj(
                source,
                self.bucket,
                object_key,
                ExtraArgs={"ContentType": content_type},
            )
        except Exception as exc:
            raise self._normalize_error("upload", exc) from exc

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

    def verify_uploaded_content(
        self,
        object_key: str,
        *,
        declared_mime_type: str,
        sample_bytes: int = 4096,
    ) -> None:
        """Verify an uploaded object's magic bytes match its declared MIME type.

        After a client PUT completes the server downloads the first ``sample_bytes`` of the
        stored object and asks libmagic (via ``python-magic``) to identify the actual MIME
        type. When that disagrees with the declared MIME type stored at upload reservation
        time the upload is rejected as ``MIME_MISMATCH`` and the object is deleted to avoid
        leaving attacker-controlled bytes in private storage.
        """
        try:
            body = self.client.get_object(
                Bucket=self.bucket, Key=object_key, Range=f"bytes=0-{sample_bytes - 1}"
            )["Body"].read()
        except Exception as exc:
            raise ObjectStorageRequestError("get_object", retryable=False) from exc
        detected = _detect_mime_type(body)
        if not _mime_matches(detected, declared_mime_type):
            # Best-effort cleanup: delete the offending object so private storage does not
            # retain content that fails verification. A delete failure does not mask the
            # verification error.
            try:
                self.delete(object_key)
            except ObjectStorageRequestError:
                pass
            raise UploadVerificationError(
                code="MIME_MISMATCH",
                message=(
                    f"Uploaded object content (detected MIME {detected!r}) does not match "
                    f"declared MIME type {declared_mime_type!r}."
                ),
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
