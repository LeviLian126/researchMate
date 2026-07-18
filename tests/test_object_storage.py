from pydantic import SecretStr

from researchmate_api.config import Settings
from researchmate_api.services.object_storage import R2ObjectStorage


class FakeS3Client:
    def __init__(self) -> None:
        self.presign_call = None
        self.deleted = None
        self.downloaded = None

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


def r2_settings() -> Settings:
    return Settings(
        app_env="test",
        llm_provider="fake",
        r2_account_id="account",
        r2_access_key_id=SecretStr("access"),
        r2_secret_access_key=SecretStr("secret"),
        r2_bucket="researchmate-test",
    )


def test_r2_adapter_presigns_and_normalizes_metadata(tmp_path) -> None:
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
