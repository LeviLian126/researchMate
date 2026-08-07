"""Verify S3-compatible upload signing, metadata, and credential selection."""

import pytest
from pydantic import SecretStr
from researchmate_api.config import Settings
from researchmate_api.services.object_storage import (
    R2ObjectStorage,
    S3CompatibleObjectStorage,
    UploadVerificationError,
    _detect_mime_type,
    _mime_matches,
)

# MIME verification depends on the optional python-magic library. When libmagic is
# not installed the verifier fails open, so tests that assert a mismatch rejection
# must be skipped rather than report a false failure.
try:
    import magic  # noqa: F401

    _HAS_MAGIC = True
except ModuleNotFoundError:
    _HAS_MAGIC = False

_skip_no_magic = pytest.mark.skipif(not _HAS_MAGIC, reason="python-magic not installed")


class FakeS3Client:
    """Record private S3 operations and return deterministic metadata."""

    def __init__(self) -> None:
        self.presign_call = None
        self.deleted = None
        self.downloaded = None
        self.fetched_bytes: dict[str, bytes] = {}

    def generate_presigned_url(self, operation, **kwargs):
        self.presign_call = (operation, kwargs)
        return "https://upload.example.test/signed"

    def head_object(self, **kwargs):
        return {
            "ContentLength": 123,
            "ContentType": "application/pdf",
            "ETag": '"etag-value"',
            "Metadata": {"parser": "pending"},
        }

    def delete_object(self, **kwargs):
        self.deleted = kwargs

    def download_fileobj(self, bucket, key, target):
        self.downloaded = (bucket, key)
        target.write(b"document bytes")

    def get_object(self, *, Bucket, Key, Range=None):  # noqa: N803 - mirrors boto3 kwargs.
        """Return a fake S3 get_object body whose bytes are configurable per object key."""
        body = self.fetched_bytes.get(Key, b"document bytes")

        class _Body:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self) -> bytes:
                return self._data

        return {"Body": _Body(body)}


def r2_settings() -> Settings:
    """Build complete legacy R2 settings for adapter tests."""
    return Settings(
        app_env="test",
        llm_provider="fake",
        r2_account_id="account",
        r2_access_key_id=SecretStr("access"),
        r2_secret_access_key=SecretStr("secret"),
        r2_bucket="researchmate-test",
    )


def test_r2_adapter_presigns_and_normalizes_metadata(tmp_path) -> None:
    """Verify R2 signing, metadata normalization, and downloads."""
    client = FakeS3Client()
    storage = R2ObjectStorage(r2_settings(), client=client)

    url = storage.presign_upload("users/u/document.pdf", content_type="application/pdf")
    metadata = storage.head("users/u/document.pdf")
    destination = tmp_path / "document.pdf"
    storage.download_to_file("users/u/document.pdf", destination)
    storage.delete("users/u/document.pdf")

    assert url == "https://upload.example.test/signed"
    assert client.presign_call == (
        "put_object",
        {
            "Params": {
                "Bucket": "researchmate-test",
                "Key": "users/u/document.pdf",
                "ContentType": "application/pdf",
            },
            "ExpiresIn": 600,
            "HttpMethod": "PUT",
        },
    )
    assert metadata.size_bytes == 123
    assert metadata.etag == "etag-value"
    assert destination.read_bytes() == b"document bytes"
    assert client.downloaded == ("researchmate-test", "users/u/document.pdf")
    assert client.deleted == {"Bucket": "researchmate-test", "Key": "users/u/document.pdf"}


def test_generic_s3_endpoint_uses_its_own_credential_set() -> None:
    """Keep generic S3 credentials separate from legacy R2 values."""
    settings = Settings(
        app_env="test",
        llm_provider="fake",
        object_storage_endpoint_url="https://example.supabase.co/storage/v1/s3",
        object_storage_access_key_id=SecretStr("generic-access"),
        object_storage_secret_access_key=SecretStr("generic-secret"),
        object_storage_bucket="researchmate-test",
        object_storage_region="us-east-1",
    )

    storage = S3CompatibleObjectStorage(settings, client=FakeS3Client())

    assert settings.uses_generic_object_storage is True
    assert settings.object_storage_configured is True
    assert storage.bucket == "researchmate-test"


# --------------------------------------------------------------------------- #
# Server-side uploaded content validation via python-magic                    #
# --------------------------------------------------------------------------- #

# A small valid PDF magic header followed by fake body content. libmagic recognises the
# leading %PDF-1.x sequence as application/pdf on any platform that ships a C magic DB.
_PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>\nendobj\ntrailer<<>>\n%%EOF"
_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"


def test_verify_uploaded_content_accepts_matching_magic_bytes() -> None:
    """Allow the upload when the stored bytes match the declared MIME type."""
    client = FakeS3Client()
    client.fetched_bytes["users/u/document.pdf"] = _PDF_BYTES
    storage = S3CompatibleObjectStorage(r2_settings(), client=client)

    # No exception is raised for a matching upload.
    storage.verify_uploaded_content("users/u/document.pdf", declared_mime_type="application/pdf")

    assert client.deleted is None


@_skip_no_magic
def test_verify_uploaded_content_rejects_disguised_upload_and_deletes_object() -> None:
    """Reject and delete an uploaded object whose bytes do not match its declared MIME."""
    client = FakeS3Client()
    client.fetched_bytes["users/u/document.pdf"] = _PNG_BYTES
    storage = S3CompatibleObjectStorage(r2_settings(), client=client)

    with pytest.raises(UploadVerificationError) as raised:
        storage.verify_uploaded_content(
            "users/u/document.pdf", declared_mime_type="application/pdf"
        )

    assert raised.value.code == "MIME_MISMATCH"
    assert "application/pdf" in str(raised.value)
    # The offending object must be removed so private storage does not retain disguised files.
    assert client.deleted == {"Bucket": "researchmate-test", "Key": "users/u/document.pdf"}


def test_verify_uploaded_content_fails_open_when_libmagic_missing(monkeypatch) -> None:
    """Fail open when the optional python-magic library is unavailable."""
    monkeypatch.setattr(
        "researchmate_api.services.object_storage._detect_mime_type",
        lambda _data: None,
    )
    client = FakeS3Client()
    client.fetched_bytes["users/u/document.pdf"] = b"not really a pdf"
    storage = S3CompatibleObjectStorage(r2_settings(), client=client)

    # Without libmagic available the verifier cannot compare bytes; it must accept the upload
    # and leave the stored object intact rather than blocking legitimate traffic.
    storage.verify_uploaded_content("users/u/document.pdf", declared_mime_type="application/pdf")
    assert client.deleted is None


def test_mime_matches_handles_aliases_for_office_documents() -> None:
    """Accept the libmagic aliases that map to declared Office MIME types."""
    assert _mime_matches("application/pdf", "application/pdf") is True
    assert _mime_matches("image/png", "image/png") is True
    # Office document types are detected as zip containers by some libmagic builds.
    assert _mime_matches("application/zip", _OFFICE_DOC_MIME) is True
    assert (
        _mime_matches(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            _OFFICE_DOC_MIME,
        )
        is True
    )
    # Cross-type mismatch must always reject.
    assert _mime_matches("image/png", "application/pdf") is False
    assert _mime_matches("application/pdf", "image/png") is False
    # Unknown declared type falls back to a tolerant prefix comparison.
    assert _mime_matches("application/x-custom", "application/x-custom") is True


def test_detect_mime_type_returns_none_for_empty_buffer() -> None:
    """Skip detection when there are no bytes to inspect."""
    assert _detect_mime_type(b"") is None


_OFFICE_DOC_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
