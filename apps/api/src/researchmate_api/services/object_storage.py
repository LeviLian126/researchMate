"""Wrap private S3-compatible object operations behind normalized errors."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import IO, Any
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from researchmate_api.config import Settings
from researchmate_api.schemas.document import MAX_DOCUMENT_UPLOAD_BYTES, MIME_BY_TYPE


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
    "application/x-ipynb+json": ("application/json", "text/plain", "ascii"),
    "application/x-ndjson": ("application/json", "text/plain", "ascii"),
    "application/jsonl": ("application/json", "text/plain", "ascii"),
    "application/xml": ("application/xml", "text/xml", "text/plain", "ascii"),
    "application/yaml": ("text/plain", "ascii"),
    "application/toml": ("text/plain", "ascii"),
    "application/sql": ("text/plain", "ascii"),
    "application/x-sh": ("text/plain", "ascii"),
    "application/x-httpd-php": ("text/plain", "ascii"),
    "application/x-ruby": ("text/plain", "ascii"),
    "application/x-tex": ("text/plain", "ascii"),
    "application/javascript": ("text/plain", "javascript", "ascii"),
    "application/typescript": ("text/plain", "typescript", "ascii"),
}
_OOXML_PACKAGE_CONTRACTS: dict[str, tuple[str, str]] = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "word/document.xml",
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document",
    ),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "ppt/presentation.xml",
        "{http://schemas.openxmlformats.org/presentationml/2006/main}presentation",
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "xl/workbook.xml",
        "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbook",
    ),
}
_OOXML_CONTENT_TYPES_ROOT = "{http://schemas.openxmlformats.org/package/2006/content-types}Types"
_OOXML_RELATIONSHIPS_ROOT = (
    "{http://schemas.openxmlformats.org/package/2006/relationships}Relationships"
)
_OOXML_OVERRIDE_TAG = "{http://schemas.openxmlformats.org/package/2006/content-types}Override"
_OOXML_RELATIONSHIP_TAG = (
    "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
)
_OOXML_VERIFICATION_XML_BYTES = 1 * 1024 * 1024
_TEXTUAL_DECLARED_MIME_TYPES = frozenset(
    mime_type
    for file_type, mime_types in MIME_BY_TYPE.items()
    if file_type not in {"pdf", "docx", "pptx", "xlsx"}
    for mime_type in mime_types
)
_TEXTUAL_DETECTED_MIME_TYPES = frozenset(
    {
        "application/json",
        "application/xml",
        "application/javascript",
        "application/x-empty",
        "inode/x-empty",
    }
)


def _detect_mime_type(data: bytes) -> str | None:
    """Return the libmagic-detected MIME type for the first chunk of bytes.

    The python-magic library is loaded lazily, but it is required at the upload boundary.
    An unavailable or failed detector is an explicit service failure instead of permission
    to accept attacker-controlled bytes without verification.
    """
    if not data:
        return None
    try:
        import magic
    except ImportError as exc:
        raise ObjectStorageRequestError("mime_detection", retryable=False) from exc
    try:
        detected = magic.from_buffer(data, mime=True)
    except Exception as exc:  # pragma: no cover - native library failures are environment-specific.
        raise ObjectStorageRequestError("mime_detection", retryable=False) from exc
    return str(detected) if detected else None


def _mime_matches(detected: str | None, declared: str) -> bool:
    """Return True when the detected MIME is a known alias of the declared type."""
    if detected is None:
        return False
    declared_lower = declared.lower()
    detected_lower = detected.lower().split(";", maxsplit=1)[0].strip()
    if declared_lower in _TEXTUAL_DECLARED_MIME_TYPES and (
        detected_lower.startswith("text/") or detected_lower in _TEXTUAL_DETECTED_MIME_TYPES
    ):
        return True
    aliases = _MIME_MAGIC_ALIASES.get(declared_lower)
    if aliases:
        return any(alias in detected_lower for alias in aliases)
    if declared_lower.startswith("text/") and any(
        marker in detected_lower for marker in ("text/", "ascii", "json", "xml")
    ):
        return True
    # Unknown-to-the-allowlist declared type: accept when libmagic agrees with the declared
    # type itself (covers rare types not enumerated above).
    return declared_lower in detected_lower or detected_lower.startswith(declared_lower)


def _matches_ooxml_package(data: bytes, declared_mime_type: str) -> bool:
    """Verify the minimal content-type, relationship, and XML identity of an OOXML package."""
    contract = _OOXML_PACKAGE_CONTRACTS.get(declared_mime_type.lower())
    if contract is None:
        return True
    core_member, expected_root = contract
    try:
        with ZipFile(BytesIO(data)) as archive:
            members = {
                name.replace("\\", "/").strip("/").lower(): name for name in archive.namelist()
            }
            required = {"[content_types].xml", "_rels/.rels", core_member.lower()}
            if not required.issubset(members):
                return False

            def read_xml(member: str) -> ElementTree.Element:
                with archive.open(members[member.lower()]) as stream:
                    payload = stream.read(_OOXML_VERIFICATION_XML_BYTES + 1)
                if len(payload) > _OOXML_VERIFICATION_XML_BYTES:
                    raise ValueError("OOXML verification XML exceeds its boundary")
                return ElementTree.fromstring(payload)

            content_types = read_xml("[content_types].xml")
            relationships = read_xml("_rels/.rels")
            core = read_xml(core_member)
    except (BadZipFile, KeyError, OSError, ValueError, ElementTree.ParseError):
        return False
    if content_types.tag != _OOXML_CONTENT_TYPES_ROOT:
        return False
    if relationships.tag != _OOXML_RELATIONSHIPS_ROOT or core.tag != expected_root:
        return False
    has_content_type = any(
        child.tag == _OOXML_OVERRIDE_TAG
        and child.attrib.get("PartName", "").lstrip("/").lower() == core_member.lower()
        and child.attrib.get("ContentType", "").lower() == declared_mime_type.lower()
        for child in content_types
    )
    has_office_relationship = any(
        child.tag == _OOXML_RELATIONSHIP_TAG
        and child.attrib.get("Target", "").lstrip("/").lower() == core_member.lower()
        and child.attrib.get("Type", "").rstrip("/").endswith("/officeDocument")
        for child in relationships
    )
    return has_content_type and has_office_relationship


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
        if detected is None:
            raise ObjectStorageRequestError("mime_detection", retryable=False)
        content_matches = _mime_matches(detected, declared_mime_type)
        if content_matches and declared_mime_type.lower() in _OOXML_PACKAGE_CONTRACTS:
            try:
                full_body = self.client.get_object(Bucket=self.bucket, Key=object_key)["Body"].read(
                    MAX_DOCUMENT_UPLOAD_BYTES + 1
                )
            except Exception as exc:
                raise ObjectStorageRequestError("get_object", retryable=False) from exc
            content_matches = len(
                full_body
            ) <= MAX_DOCUMENT_UPLOAD_BYTES and _matches_ooxml_package(full_body, declared_mime_type)
        if not content_matches:
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
