from functools import lru_cache

import boto3
from botocore.client import Config
from django.conf import settings


class DocumentStorage:
    def __init__(self):
        common = {
            "aws_access_key_id": settings.MINIO_ACCESS_KEY,
            "aws_secret_access_key": settings.MINIO_SECRET_KEY,
            "region_name": settings.MINIO_REGION,
            "verify": settings.MINIO_VERIFY_SSL,
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        self.internal = boto3.client(
            "s3", endpoint_url=settings.MINIO_INTERNAL_ENDPOINT, **common
        )
        self.public = boto3.client(
            "s3", endpoint_url=settings.MINIO_PUBLIC_ENDPOINT, **common
        )
        self.bucket = settings.MINIO_BUCKET_NAME

    def upload(self, key, file_obj, content_type, checksum=""):
        self.internal.upload_fileobj(
            file_obj,
            self.bucket,
            key,
            ExtraArgs={
                "ContentType": content_type,
                "Metadata": {"checksum-sha256": checksum},
            },
        )

    def copy(self, source_key, destination_key):
        self.internal.copy_object(
            Bucket=self.bucket,
            Key=destination_key,
            CopySource={"Bucket": self.bucket, "Key": source_key},
        )

    def head(self, key):
        return self.internal.head_object(Bucket=self.bucket, Key=key)

    def delete(self, key):
        if key:
            self.internal.delete_object(Bucket=self.bucket, Key=key)

    def list_staging(self):
        paginator = self.internal.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix="staging/"):
            yield from page.get("Contents", [])

    def presigned_download(self, key, filename, expires):
        return self.public.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=expires,
        )


@lru_cache(maxsize=1)
def get_storage() -> DocumentStorage:
    return DocumentStorage()
