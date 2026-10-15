import uuid

from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import record_document_audit

from .keys import staging_key
from .models import Document, DocumentStatus, ProcessingKind
from .storage import get_storage


def _schedule(task, *args):
    transaction.on_commit(lambda: task.delay(*args))


def create_document(*, owner, title, upload, file_metadata, request=None):
    document_id = uuid.uuid4()
    operation_id = uuid.uuid4()
    key = staging_key(document_id)
    storage = get_storage()
    storage.upload(
        key,
        upload,
        file_metadata["content_type"],
        file_metadata["checksum_sha256"],
    )
    try:
        with transaction.atomic():
            document = Document.objects.create(
                id=document_id,
                title=title,
                owner=owner,
                staging_object_key=key,
                status=DocumentStatus.PENDING,
                processing_kind=ProcessingKind.CREATE,
                operation_id=operation_id,
                **file_metadata,
            )
            record_document_audit(
                document=document,
                actor=owner,
                request=request,
                action=AuditAction.CREATE_REQUESTED,
            )
            from .tasks import finalize_document

            _schedule(finalize_document, str(document.pk), str(operation_id))
        return document
    except Exception:
        storage.delete(key)
        raise


def update_document(
    *, document, actor, title=None, upload=None, file_metadata=None, request=None
):
    staged_key = None
    operation_id = None
    if upload:
        operation_id = uuid.uuid4()
        staged_key = staging_key(document.pk)
        get_storage().upload(
            staged_key,
            upload,
            file_metadata["content_type"],
            file_metadata["checksum_sha256"],
        )
    try:
        with transaction.atomic():
            locked = Document.objects.select_for_update().get(pk=document.pk)
            if locked.status in (
                DocumentStatus.DELETING,
                DocumentStatus.PENDING,
                DocumentStatus.PROCESSING,
            ):
                raise ValueError("Document is not currently updateable.")
            if title is not None:
                locked.title = title
            if upload:
                old_staging = locked.staging_object_key
                locked.staging_object_key = staged_key
                locked.operation_id = operation_id
                locked.processing_kind = ProcessingKind.REPLACE
                locked.pending_original_filename = file_metadata["original_filename"]
                locked.pending_content_type = file_metadata["content_type"]
                locked.pending_size_bytes = file_metadata["size_bytes"]
                locked.pending_checksum_sha256 = file_metadata["checksum_sha256"]
                locked.processing_error = ""
                if old_staging:
                    transaction.on_commit(lambda: get_storage().delete(old_staging))
            locked.save()
            record_document_audit(
                document=locked,
                actor=actor,
                request=request,
                action=AuditAction.UPDATE_REQUESTED if upload else AuditAction.UPDATE,
            )
            if upload:
                from .tasks import replace_document_file

                _schedule(replace_document_file, str(locked.pk), str(operation_id))
            else:
                from .events import publish_document_event

                transaction.on_commit(
                    lambda: publish_document_event("document_updated")
                )
        return locked
    except Exception:
        if staged_key:
            get_storage().delete(staged_key)
        raise


def delete_document(*, document, actor, request=None):
    with transaction.atomic():
        locked = Document.objects.select_for_update().get(pk=document.pk)
        locked.status = DocumentStatus.DELETING
        locked.processing_kind = ProcessingKind.NONE
        locked.operation_id = uuid.uuid4()
        locked.save(
            update_fields=("status", "processing_kind", "operation_id", "updated_at")
        )
        record_document_audit(
            document=locked,
            actor=actor,
            request=request,
            action=AuditAction.DELETE_REQUESTED,
        )
        from .tasks import delete_document_objects

        _schedule(delete_document_objects, str(locked.pk), str(locked.operation_id))
    return locked
