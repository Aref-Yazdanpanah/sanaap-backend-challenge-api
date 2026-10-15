from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.documents.storage import get_storage


class Command(BaseCommand):
    help = "Idempotently create the private MinIO document bucket."

    def handle(self, *args, **options):
        storage = get_storage()
        try:
            storage.internal.head_bucket(Bucket=storage.bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            kwargs = {"Bucket": storage.bucket}
            if settings.MINIO_REGION != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {
                    "LocationConstraint": settings.MINIO_REGION
                }
            storage.internal.create_bucket(**kwargs)

        # MinIO buckets are private by default.  Removing any pre-existing
        # anonymous policy also makes this command safely idempotent for reused
        # development volumes.  MinIO does not implement AWS's
        # PutPublicAccessBlock API consistently across releases.
        try:
            storage.internal.delete_bucket_policy(Bucket=storage.bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in {"NoSuchBucketPolicy", "NoSuchPolicy", "404"}:
                raise
        self.stdout.write(self.style.SUCCESS(f"Private bucket ready: {storage.bucket}"))
