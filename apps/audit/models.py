import uuid

from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    CREATE_REQUESTED = "CREATE_REQUESTED", "Create requested"
    CREATE = "CREATE", "Create completed"
    RETRIEVE = "RETRIEVE", "Retrieved"
    DOWNLOAD_LINK_ISSUED = "DOWNLOAD_LINK_ISSUED", "Download link issued"
    UPDATE_REQUESTED = "UPDATE_REQUESTED", "Update requested"
    UPDATE = "UPDATE", "Updated"
    DELETE_REQUESTED = "DELETE_REQUESTED", "Delete requested"
    DELETE = "DELETE", "Deleted"
    ACCESS_DENIED = "ACCESS_DENIED", "Access denied"


class AuditResult(models.TextChoices):
    SUCCESS = "SUCCESS", "Success"
    FAILURE = "FAILURE", "Failure"
    DENIED = "DENIED", "Denied"


class DocumentAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_audits",
    )
    actor_id_snapshot = models.CharField(max_length=64, blank=True)
    actor_username_snapshot = models.CharField(max_length=150, blank=True)
    document = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    document_id_snapshot = models.UUIDField(db_index=True)
    document_title_snapshot = models.CharField(max_length=255)
    action = models.CharField(max_length=32, choices=AuditAction.choices, db_index=True)
    result = models.CharField(
        max_length=16, choices=AuditResult.choices, default=AuditResult.SUCCESS
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("actor_id_snapshot", "-created_at"),
                name="audit_actor_created_idx",
            ),
            models.Index(
                fields=("action", "-created_at"), name="audit_action_created_idx"
            ),
        ]
