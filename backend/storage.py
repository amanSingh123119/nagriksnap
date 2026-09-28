"""Private evidence storage adapter.

S3-compatible mode requires a private bucket and server-side encryption configured
at the provider. This module never generates public URLs. Local mode is for development only.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
    else:
        load_dotenv()
except ImportError:
    pass

BACKEND_DIR = Path(__file__).resolve().parent
LOCAL_UPLOAD_DIR = Path(os.getenv("NAGRIKSNAP_LOCAL_UPLOAD_DIR", str(BACKEND_DIR / "uploads")))
STORAGE_MODE = os.getenv("EVIDENCE_STORAGE_MODE", "local").strip().lower()
S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
S3_REGION = os.getenv("S3_REGION", "").strip() or None
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "").strip() or None
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "").strip() or None
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip() or None


def _s3_client():
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("S3 evidence storage requires boto3; install backend requirements") from exc
    kwargs = {}
    if S3_REGION:
        kwargs["region_name"] = S3_REGION
    if S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = S3_ENDPOINT_URL
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **kwargs)


def validate_configuration():
    if STORAGE_MODE not in {"local", "s3"}:
        raise RuntimeError("EVIDENCE_STORAGE_MODE must be 'local' or 's3'")
    if STORAGE_MODE == "s3" and not S3_BUCKET:
        raise RuntimeError("S3_BUCKET is required when EVIDENCE_STORAGE_MODE=s3")


def generate_presigned_download_url(filename: str, expires_in: int = 3600) -> str | None:
    """Generate a temporary signed URL for authorized S3 download."""
    validate_configuration()
    if STORAGE_MODE != "s3":
        return None
    client = _s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": filename},
        ExpiresIn=max(60, min(expires_in, 86400))
    )


def verify_storage_health() -> dict:
    """Verify configured storage adapter health."""
    if STORAGE_MODE == "s3":
        return {"mode": "s3", "bucket": S3_BUCKET, "region": S3_REGION, "status": "configured"}
    upload_dir = LOCAL_UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    return {"mode": "local", "path": str(upload_dir), "status": "ready"}


def save_evidence(filename: str, content: bytes, content_type: str) -> str:
    """Persist evidence and return an opaque storage key, never a public URL."""
    validate_configuration()
    if Path(filename).name != filename or filename in {"", ".", ".."}:
        raise ValueError("Invalid evidence filename")
    if STORAGE_MODE == "s3":
        _s3_client().put_object(Bucket=S3_BUCKET, Key=filename, Body=content,
                                ContentType=content_type, ServerSideEncryption="AES256")
    else:
        LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        target = LOCAL_UPLOAD_DIR / filename
        with target.open("xb") as handle:
            handle.write(content)
    return filename


def read_evidence(filename: str):
    """Return (bytes, content_type) from private storage; caller must authorize access."""
    validate_configuration()
    if Path(filename).name != filename or filename in {"", ".", ".."}:
        return None
    if STORAGE_MODE == "s3":
        try:
            response = _s3_client().get_object(Bucket=S3_BUCKET, Key=filename)
            return response["Body"].read(), response.get("ContentType", "application/octet-stream")
        except Exception as exc:
            # Do not leak provider errors or object existence to API callers.
            if exc.__class__.__name__ in {"NoSuchKey", "NotFound", "NoSuchBucket"}:
                return None
            try:
                from botocore.exceptions import ClientError
                if isinstance(exc, ClientError) and exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                    return None
            except ImportError:
                pass
            raise
    target = LOCAL_UPLOAD_DIR / filename
    if not target.is_file():
        return None
    media = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(target.suffix.lower(), "application/octet-stream")
    return target.read_bytes(), media
