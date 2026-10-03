import uuid
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=f"{'https' if settings.minio_use_ssl else 'http'}://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name="us-east-1",
            config=Config(signature_version="s3v4"),
        )
    return _s3_client


def generate_file_key(assignment_code: str, original_name: str) -> str:
    ext = original_name.split(".")[-1] if "." in original_name else ""
    name = f"{assignment_code}/{uuid.uuid4()}"
    if ext:
        name += f".{ext}"
    return name


def upload_file(file_bytes: bytes, key: str, content_type: str = "application/octet-stream"):
    client = get_s3_client()
    client.put_object(
        Bucket=settings.minio_bucket,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )


def get_download_url(key: str, expires_in: int = 3600) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.minio_bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def get_object_bytes(key: str) -> bytes:
    client = get_s3_client()
    response = client.get_object(Bucket=settings.minio_bucket, Key=key)
    return response["Body"].read()


def get_object_stream(key: str):
    client = get_s3_client()
    response = client.get_object(Bucket=settings.minio_bucket, Key=key)
    return response
