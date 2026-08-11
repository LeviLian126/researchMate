"""Verify S3-compatible upload signing, metadata, and credential selection."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from zipfile import ZipFile

import pytest
from pydantic import SecretStr
from researchmate_api.config import Settings
from researchmate_api.schemas.document import MIME_BY_TYPE
from researchmate_api.services.object_storage import (
    ObjectStorageRequestError,
    R2ObjectStorage,
    S3CompatibleObjectStorage,
    UploadVerificationError,
    _detect_mime_type,
    _mime_matches,
)


class FakeS3Client:
    """Record private S3 operations and return deterministic metadata."""

    def __init__(self) -> None:
        self.presign_call = None
        self.deleted = None
        self.downloaded = None
        self.uploaded = None
        self.fetched_bytes: dict[str, bytes] = {}

    def generate_presigned_url(self, operation: str, **kwargs: Any) -> str:
        self.presign_call = (operation, kwargs)
        return "https://upload.example.test/signed"

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "ContentLength": 123,
            "ContentType": "application/pdf",
            "ETag": '"etag-value"',
            "Metadata": {"parser": "pending"},
        }

    def delete_object(self, **kwargs: Any) -> None:
        self.deleted = kwargs

    def download_fileobj(
        self, bucket: str, key: str, target: Any
    ) -> None:  # boundary: opaque test double (file-like)
        self.downloaded = (bucket, key)
        target.write(b"document bytes")

    def upload_fileobj(
        self, source: Any, bucket: str, key: str, *, ExtraArgs: dict[str, str]
    ) -> None:  # boundary: opaque boto3-compatible stream
        """Record the proxied upload bytes and provider metadata."""
        self.uploaded = (source.read(), bucket, key, ExtraArgs)

    def get_object(  # noqa: N803 - mirrors boto3 kwargs.
        self, *, Bucket: str, Key: str, Range: str | None = None
    ) -> dict[str, Any]:
        """Return a fake S3 get_object body whose bytes are configurable per object key."""
        body = self.fetched_bytes.get(Key, b"document bytes")

        class _Body:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self, size: int = -1) -> bytes:
                return self._data if size < 0 else self._data[:size]

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


def test_s3_adapter_uploads_server_received_stream() -> None:
    """Keep proxy uploads private and preserve their verified MIME metadata."""
    client = FakeS3Client()
    storage = S3CompatibleObjectStorage(r2_settings(), client=client)

    storage.upload_stream(
        "users/u/document.pdf", BytesIO(b"pdf bytes"), content_type="application/pdf"
    )

    assert client.uploaded == (
        b"pdf bytes",
        "researchmate-test",
        "users/u/document.pdf",
        {"ContentType": "application/pdf"},
    )


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


def test_verify_uploaded_content_fails_closed_when_libmagic_missing(monkeypatch) -> None:
    """Reject unverifiable uploads when the required MIME detector is unavailable."""
    monkeypatch.setattr(
        "researchmate_api.services.object_storage._detect_mime_type",
        lambda _data: None,
    )
    client = FakeS3Client()
    client.fetched_bytes["users/u/document.pdf"] = b"not really a pdf"
    storage = S3CompatibleObjectStorage(r2_settings(), client=client)

    with pytest.raises(ObjectStorageRequestError, match="mime_detection"):
        storage.verify_uploaded_content(
            "users/u/document.pdf", declared_mime_type="application/pdf"
        )


@pytest.mark.parametrize(
    ("detected", "declared"),
    [
        ("text/plain", "application/csv"),
        ("text/xml", "text/plain"),
        ("text/html", "application/xhtml+xml"),
        ("text/plain", "application/x-yaml"),
    ],
)
def test_mime_matches_every_textual_public_alias(detected: str, declared: str) -> None:
    """Keep upload reservation aliases compatible with completion-time detection."""
    assert _mime_matches(detected, declared) is True


def test_every_public_textual_mime_accepts_plain_text_detection() -> None:
    """Prevent future reservation aliases from drifting away from byte verification."""
    binary_types = {"pdf", "docx", "pptx", "xlsx"}

    assert all(
        _mime_matches("text/plain", declared)
        for file_type, declared_types in MIME_BY_TYPE.items()
        if file_type not in binary_types
        for declared in declared_types
    )


def test_verify_uploaded_content_rejects_generic_zip_disguised_as_xlsx() -> None:
    """Require XLSX package structure instead of accepting every ZIP archive."""
    disguised = BytesIO()
    with ZipFile(disguised, "w") as archive:
        archive.writestr("notes.txt", "not a workbook")
    client = FakeS3Client()
    client.fetched_bytes["users/u/not-a-workbook.xlsx"] = disguised.getvalue()
    storage = S3CompatibleObjectStorage(r2_settings(), client=client)

    with pytest.raises(UploadVerificationError, match="does not match"):
        storage.verify_uploaded_content(
            "users/u/not-a-workbook.xlsx",
            declared_mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    assert client.deleted == {
        "Bucket": "researchmate-test",
        "Key": "users/u/not-a-workbook.xlsx",
    }


def test_verify_uploaded_content_rejects_ooxml_member_name_without_package_contract() -> None:
    """Reject a ZIP that copies one OOXML filename without relationships or content types."""
    workbook = BytesIO()
    with ZipFile(workbook, "w") as archive:
        archive.writestr("xl/workbook.xml", "not XML")
    client = FakeS3Client()
    client.fetched_bytes["users/u/counterfeit.xlsx"] = workbook.getvalue()
    storage = S3CompatibleObjectStorage(r2_settings(), client=client)

    with pytest.raises(UploadVerificationError, match="does not match"):
        storage.verify_uploaded_content(
            "users/u/counterfeit.xlsx",
            declared_mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def test_verify_uploaded_content_rejects_bogus_ooxml_contract_elements() -> None:
    """Require namespace-qualified Override and Relationship elements, not copied attributes."""
    declared_mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    package = BytesIO()
    with ZipFile(package, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            f'<Bogus PartName="/xl/workbook.xml" ContentType="{declared_mime_type}"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Bogus Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
        )
    client = FakeS3Client()
    client.fetched_bytes["users/u/bogus.xlsx"] = package.getvalue()
    storage = S3CompatibleObjectStorage(r2_settings(), client=client)

    with pytest.raises(UploadVerificationError, match="does not match"):
        storage.verify_uploaded_content(
            "users/u/bogus.xlsx",
            declared_mime_type=declared_mime_type,
        )


@pytest.mark.parametrize(
    ("extension", "declared_mime_type", "core_member", "core_xml"),
    [
        (
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "word/document.xml",
            '<document xmlns="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
        ),
        (
            "pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "ppt/presentation.xml",
            '<presentation xmlns="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        ),
        (
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
        ),
    ],
)
def test_verify_uploaded_content_accepts_minimal_valid_ooxml_package(
    extension: str,
    declared_mime_type: str,
    core_member: str,
    core_xml: str,
) -> None:
    """Accept each OOXML family only when its package identity is internally consistent."""
    package = BytesIO()
    with ZipFile(package, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            f'<Override PartName="/{core_member}" ContentType="{declared_mime_type}"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            f'Target="{core_member}"/>'
            "</Relationships>",
        )
        archive.writestr(core_member, core_xml)
    object_key = f"users/u/document.{extension}"
    client = FakeS3Client()
    client.fetched_bytes[object_key] = package.getvalue()
    storage = S3CompatibleObjectStorage(r2_settings(), client=client)

    storage.verify_uploaded_content(object_key, declared_mime_type=declared_mime_type)

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
    assert _mime_matches("text/plain", "text/markdown") is True
    assert _mime_matches("application/json", "application/x-ipynb+json") is True


def test_detect_mime_type_returns_none_for_empty_buffer() -> None:
    """Skip detection when there are no bytes to inspect."""
    assert _detect_mime_type(b"") is None


_OFFICE_DOC_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
