from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.documents.models import Document
from apps.documents.storage import get_storage


class Command(BaseCommand):
    help = "Delete orphan MinIO staging objects older than the configured age."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-hours", type=int, default=24)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=options["older_than_hours"])
        active = set(
            Document.objects.exclude(staging_object_key__isnull=True).values_list(
                "staging_object_key", flat=True
            )
        )
        removed = 0
        storage = get_storage()
        for item in storage.list_staging():
            key = item["Key"]
            if key not in active and item["LastModified"] < cutoff:
                self.stdout.write(f"orphan: {key}")
                if not options["dry_run"]:
                    storage.delete(key)
                removed += 1
        self.stdout.write(self.style.SUCCESS(f"Orphan objects found: {removed}"))
