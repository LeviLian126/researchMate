"""Configure CORS on the Supabase Storage S3 bucket for direct browser uploads.

Presigned S3 URLs let the browser upload directly to *.supabase.co, bypassing
corporate/ISP proxies that intercept *.vercel.app and return 502 for large PUT
bodies. For this to work, the bucket must return CORS headers that allow the
frontend origin to perform cross-origin PUT requests.

Usage (from the repository root):

    python scripts/configure_storage_cors.py

Environment variables (read from .env or the shell):

    OBJECT_STORAGE_ENDPOINT_URL   e.g. https://<ref>.storage.supabase.co/storage/v1/s3
    OBJECT_STORAGE_ACCESS_KEY_ID  S3 access key
    OBJECT_STORAGE_SECRET_ACCESS_KEY  S3 secret key
    OBJECT_STORAGE_BUCKET         e.g. researchmate-dev
    OBJECT_STORAGE_REGION         e.g. ca-central-1
    CORS_ALLOWED_ORIGINS          e.g. https://research-mate-web.vercel.app

If the S3-compatible API does not support PutBucketCors, the script prints the
manual Dashboard steps instead.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env() -> None:
    """Load .env so the script works without manual exports."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    """Apply CORS rules to the configured S3-compatible bucket."""
    _load_env()

    endpoint = os.getenv("OBJECT_STORAGE_ENDPOINT_URL")
    access_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY_ID")
    secret_key = os.getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY")
    bucket = os.getenv("OBJECT_STORAGE_BUCKET")
    region = os.getenv("OBJECT_STORAGE_REGION", "auto")
    origins = os.getenv("CORS_ALLOWED_ORIGINS", "")

    missing = [
        name
        for name, val in [
            ("OBJECT_STORAGE_ENDPOINT_URL", endpoint),
            ("OBJECT_STORAGE_ACCESS_KEY_ID", access_key),
            ("OBJECT_STORAGE_SECRET_ACCESS_KEY", secret_key),
            ("OBJECT_STORAGE_BUCKET", bucket),
            ("CORS_ALLOWED_ORIGINS", origins),
        ]
        if not val
    ]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        return 1

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("boto3 is not installed. Run: pip install boto3", file=sys.stderr)
        return 1

    allowed_origins = [o.strip() for o in origins.split(",") if o.strip()]
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    cors_config = {
        "CORSRules": [
            {
                "AllowedOrigins": allowed_origins,
                "AllowedMethods": ["PUT", "GET", "HEAD"],
                "AllowedHeaders": ["Content-Type", "Content-Length"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3600,
            }
        ]
    }

    try:
        client.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors_config)
        print(f"CORS configured on bucket '{bucket}' for origins: {allowed_origins}")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        print(
            f"PutBucketCors failed (code={code}). The S3-compatible API may not "
            "support this operation. Configure CORS manually:\n"
            "  1. Open the Supabase Dashboard > Storage > Settings\n"
            "  2. Add a CORS rule with:\n"
            f"     Allowed Origin: {allowed_origins}\n"
            "     Allowed Methods: PUT, GET, HEAD\n"
            "     Allowed Headers: Content-Type, Content-Length\n"
            "     Exposed Headers: ETag\n"
            "     Max Age: 3600",
            file=sys.stderr,
        )
        return 1

    try:
        response = client.get_bucket_cors(Bucket=bucket)
        rules = response.get("CORSRules", [])
        print(f"Verified: {len(rules)} CORS rule(s) active on bucket '{bucket}'")
    except ClientError:
        print("Warning: could not verify CORS configuration (GetBucketCors not supported).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
