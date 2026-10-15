import logging

from botocore.exceptions import BotoCoreError, ClientError
from celery import Task, shared_task
from django.db import transaction

from apps.audit.models import AuditAction, AuditResult
from apps.audit.services import record_document_audit

from .events import publish_document_event
from .keys import final_key
from .models import Document, DocumentStatus, ProcessingKind
from .storage import get_storage

logger = logging.getLogger(__name__)


TRANSIENT_STORAGE_ERRORS = (BotoCoreError, OSError, ConnectionError)
MISSING_OBJECT_CODES = {"404", "NoSuchKey", "NotFound"}


def _mark_failed(document_id, operation_id, message):
    with transaction.atomic():
        document = (
            Document.objects.select_for_update()
            .filter(pk=document_id, operation_id=operation_id)
            .first()
        )
        if not document:
            return
        if document.processing_kind == ProcessingKind.CREATE:
            document.status = DocumentStatus.FAILED
        document.processing_error = message[:500]
        document.save(update_fields=("status", "processing_error", "updated_at"))


class DocumentOperationTask(Task):
    """Persist a safe failure state after Celery exhausts storage retries."""

    autoretry_for = TRANSIENT_STORAGE_ERRORS
    retry_backoff = True
    retry_jitter = True
    max_retries = 4

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if len(args) >= 2:
            _mark_failed(
                args[0],
                args[1],
                "Storage operation failed after retry exhaustion.",
            )
        logger.error(
            "Document background operation failed after retries",
            extra={"task_id": task_id, "task_name": self.name},
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)


@shared_task(
    bind=True,
    base=DocumentOperationTask,
)
def finalize_document(self, document_id, operation_id):
    document = Document.objects.filter(pk=document_id).first()
    if not document or document.status == DocumentStatus.READY:
        return
    if (
        str(document.operation_id) != operation_id
        or document.processing_kind != ProcessingKind.CREATE
    ):
        return
    destination = document.object_key or final_key(document.pk, operation_id)
    try:
        storage = get_storage()
        try:
            head = storage.head(destination)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in MISSING_OBJECT_CODES:
                raise
            storage.copy(document.staging_object_key, destination)
            head = storage.head(destination)
        if (
            head["ContentLength"] != document.size_bytes
            or head.get("Metadata", {}).get("checksum-sha256")
            != document.checksum_sha256
        ):
            raise ValueError("Stored object size verification failed.")
        with transaction.atomic():
            locked = Document.objects.select_for_update().get(pk=document.pk)
            if (
                str(locked.operation_id) != operation_id
                or locked.processing_kind != ProcessingKind.CREATE
            ):
                storage.delete(destination)
                return
            staging = locked.staging_object_key
            locked.object_key = destination
            locked.staging_object_key = None
            locked.status = DocumentStatus.READY
            locked.processing_kind = ProcessingKind.NONE
            locked.processing_error = ""
            locked.save()
            record_document_audit(document=locked, action=AuditAction.CREATE)
            transaction.on_commit(lambda: storage.delete(staging))
            transaction.on_commit(lambda: publish_document_event("document_created"))
    except ValueError as exc:
        _mark_failed(document_id, operation_id, str(exc))
        record_document_audit(
            document=document, action=AuditAction.CREATE, result=AuditResult.FAILURE
        )
        raise


@shared_task(
    bind=True,
    base=DocumentOperationTask,
)
def replace_document_file(self, document_id, operation_id):
    document = Document.objects.filter(pk=document_id).first()
    if (
        not document
        or str(document.operation_id) != operation_id
        or document.processing_kind != ProcessingKind.REPLACE
    ):
        return
    destination = final_key(document.pk, operation_id)
    storage = get_storage()
    storage.copy(document.staging_object_key, destination)
    head = storage.head(destination)
    if (
        head["ContentLength"] != document.pending_size_bytes
        or head.get("Metadata", {}).get("checksum-sha256")
        != document.pending_checksum_sha256
    ):
        storage.delete(destination)
        _mark_failed(
            document_id, operation_id, "Stored replacement size verification failed."
        )
        return
    with transaction.atomic():
        locked = Document.objects.select_for_update().get(pk=document.pk)
        if (
            str(locked.operation_id) != operation_id
            or locked.processing_kind != ProcessingKind.REPLACE
        ):
            storage.delete(destination)
            return
        old_key, staged_key = locked.object_key, locked.staging_object_key
        locked.object_key = destination
        locked.original_filename = locked.pending_original_filename
        locked.content_type = locked.pending_content_type
        locked.size_bytes = locked.pending_size_bytes
        locked.checksum_sha256 = locked.pending_checksum_sha256
        locked.staging_object_key = None
        locked.processing_kind = ProcessingKind.NONE
        locked.operation_id = None
        locked.pending_original_filename = ""
        locked.pending_content_type = ""
        locked.pending_size_bytes = None
        locked.pending_checksum_sha256 = ""
        locked.processing_error = ""
        locked.status = DocumentStatus.READY
        locked.save()
        record_document_audit(document=locked, action=AuditAction.UPDATE)
        transaction.on_commit(lambda: storage.delete(staged_key))
        transaction.on_commit(lambda: storage.delete(old_key))
        transaction.on_commit(lambda: publish_document_event("document_updated"))


@shared_task(
    bind=True,
    base=DocumentOperationTask,
)
def delete_document_objects(self, document_id, operation_id):
    document = Document.objects.filter(pk=document_id).first()
    if not document:
        return
    if (
        document.status != DocumentStatus.DELETING
        or str(document.operation_id) != operation_id
    ):
        return
    storage = get_storage()
    storage.delete(document.object_key)
    storage.delete(document.staging_object_key)
    with transaction.atomic():
        locked = (
            Document.objects.select_for_update()
            .filter(
                pk=document_id,
                operation_id=operation_id,
                status=DocumentStatus.DELETING,
            )
            .first()
        )
        if not locked:
            return
        record_document_audit(document=locked, action=AuditAction.DELETE)
        locked.delete()
