import uuid

from django.conf import settings
from django.db import models


class DocumentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    READY = "READY", "Ready"
    FAILED = "FAILED", "Failed"
    DELETING = "DELETING", "Deleting"


class ProcessingKind(models.TextChoices):
    CREATE = "CREATE", "Create"
    REPLACE = "REPLACE", "Replace"
    NONE = "", "None"


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents"
    )
    original_filename = models.CharField(max_length=255)
    object_key = models.CharField(max_length=512, unique=True, null=True, blank=True)
    staging_object_key = models.CharField(
        max_length=512, unique=True, null=True, blank=True
    )
    content_type = models.CharField(max_length=127)
    size_bytes = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=DocumentStatus.choices,
        default=DocumentStatus.PENDING,
        db_index=True,
    )
    processing_kind = models.CharField(
        max_length=16, choices=ProcessingKind.choices, blank=True, default=""
    )
    operation_id = models.UUIDField(null=True, blank=True)
    pending_original_filename = models.CharField(max_length=255, blank=True)
    pending_content_type = models.CharField(max_length=127, blank=True)
    pending_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    pending_checksum_sha256 = models.CharField(max_length=64, blank=True)
    processing_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("owner", "-created_at", "-id"), name="doc_owner_created_idx"
            ),
            models.Index(
                fields=("status", "-created_at", "-id"), name="doc_status_created_idx"
            ),
            models.Index(fields=("content_type",), name="doc_content_type_idx"),
            models.Index(fields=("-created_at", "-id"), name="doc_created_id_idx"),
        ]

    @property
    def replacement_pending(self):
        return self.processing_kind == ProcessingKind.REPLACE and bool(
            self.staging_object_key
        )
