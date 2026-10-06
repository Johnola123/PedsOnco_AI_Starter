import hashlib
from collections.abc import Iterator

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import settings


def _client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def get_s3_client():
    return _client(settings.s3_endpoint_url)


def get_public_signing_client():
    # This client only signs URLs. The endpoint must be reachable by the browser/API client.
    return _client(settings.s3_public_endpoint_url)


def ensure_bucket() -> None:
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)

    # Allow the local React app to PUT/GET directly with presigned URLs.
    # In production, set WEB_ORIGINS to your actual HTTPS application origin(s).
    if settings.web_origin_list:
        try:
            client.put_bucket_cors(
                Bucket=settings.s3_bucket,
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedOrigins": settings.web_origin_list,
                            "AllowedMethods": ["GET", "PUT", "HEAD"],
                            "AllowedHeaders": ["*"],
                            "ExposeHeaders": ["ETag"],
                            "MaxAgeSeconds": 3600,
                        }
                    ]
                },
            )
        except ClientError:
            # Some S3-compatible providers manage CORS outside the S3 API.
            # Bucket creation should still succeed; deployment docs explain the fallback.
            pass


def generate_upload_url(object_key: str, content_type: str) -> str:
    return get_public_signing_client().generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.presign_expires_seconds,
        HttpMethod="PUT",
    )


def generate_download_url(object_key: str) -> str:
    return get_public_signing_client().generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": settings.s3_bucket, "Key": object_key},
        ExpiresIn=settings.presign_expires_seconds,
        HttpMethod="GET",
    )


def object_head(object_key: str) -> dict:
    return get_s3_client().head_object(Bucket=settings.s3_bucket, Key=object_key)


def delete_object(object_key: str) -> None:
    get_s3_client().delete_object(Bucket=settings.s3_bucket, Key=object_key)


def iter_object_chunks(object_key: str, chunk_size: int = 8 * 1024 * 1024) -> Iterator[bytes]:
    response = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=object_key)
    body = response["Body"]
    try:
        while True:
            chunk = body.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        body.close()


def sha256_for_object(object_key: str) -> str:
    digest = hashlib.sha256()
    for chunk in iter_object_chunks(object_key):
        digest.update(chunk)
    return digest.hexdigest()
