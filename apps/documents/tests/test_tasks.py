import uuid
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from apps.audit.models import AuditAction, DocumentAuditLog
from apps.documents.models import Document, DocumentStatus, ProcessingKind
from apps.documents.tasks import (
    delete_document_objects,
    finalize_document,
    replace_document_file,
)
from apps.documents.tests.test_api import make_document


@pytest.mark.django_db(transaction=True)
def test_finalize_is_idempotent(editor_user):
    operation = uuid.uuid4()
    document = Document.objects.create(
        title="pending",
        owner=editor_user,
        original_filename="a.pdf",
        staging_object_key="staging/a",
        content_type="application/pdf",
        size_bytes=10,
        checksum_sha256="a" * 64,
        status=DocumentStatus.PENDING,
        processing_kind=ProcessingKind.CREATE,
        operation_id=operation,
    )
    storage = Mock()
    storage.head.side_effect = [
        ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
            "HeadObject",
        ),
        {"ContentLength": 10, "Metadata": {"checksum-sha256": "a" * 64}},
    ]
    with (
        patch("apps.documents.tasks.get_storage", return_value=storage),
        patch("apps.documents.tasks.publish_document_event") as publish,
    ):
        finalize_document.run(str(document.pk), str(operation))
        finalize_document.run(str(document.pk), str(operation))
    document.refresh_from_db()
    assert document.status == DocumentStatus.READY
    assert storage.copy.call_count == 1
    publish.assert_called_once_with("document_created")


@pytest.mark.django_db(transaction=True)
def test_stale_finalize_does_nothing(editor_user):
    document = make_document(editor_user)
    with patch("apps.documents.tasks.get_storage") as storage:
        finalize_document.run(str(document.pk), str(uuid.uuid4()))
    storage.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_replacement_preserves_old_until_success(editor_user):
    document = make_document(editor_user)
    old_key = document.object_key
    operation = uuid.uuid4()
    document.staging_object_key = "staging/new"
    document.operation_id = operation
    document.processing_kind = ProcessingKind.REPLACE
    document.pending_original_filename = "new.pdf"
    document.pending_content_type = "application/pdf"
    document.pending_size_bytes = 12
    document.pending_checksum_sha256 = "b" * 64
    document.save()
    assert document.object_key == old_key
    storage = Mock()
    storage.head.return_value = {
        "ContentLength": 12,
        "Metadata": {"checksum-sha256": "b" * 64},
    }
    with (
        patch("apps.documents.tasks.get_storage", return_value=storage),
        patch("apps.documents.tasks.publish_document_event"),
    ):
        replace_document_file.run(str(document.pk), str(operation))
    document.refresh_from_db()
    assert document.object_key != old_key
    assert document.original_filename == "new.pdf"
    storage.delete.assert_any_call(old_key)


@pytest.mark.django_db(transaction=True)
def test_delete_removes_object_and_preserves_audit(editor_user):
    document = make_document(editor_user)
    document.status = DocumentStatus.DELETING
    document.operation_id = uuid.uuid4()
    document.save()
    document_id = document.pk
    storage = Mock()
    with patch("apps.documents.tasks.get_storage", return_value=storage):
        delete_document_objects.run(str(document.pk), str(document.operation_id))
    assert not Document.objects.filter(pk=document_id).exists()
    assert DocumentAuditLog.objects.filter(
        document_id_snapshot=document_id, action=AuditAction.DELETE
    ).exists()


@pytest.mark.django_db
def test_transient_storage_error_is_configured_for_retry(editor_user):
    document = make_document(editor_user)
    document.status = DocumentStatus.PENDING
    document.processing_kind = ProcessingKind.CREATE
    document.operation_id = uuid.uuid4()
    document.staging_object_key = "staging/retry"
    document.save()
    storage = Mock()
    storage.head.side_effect = OSError("temporary network failure")
    with patch("apps.documents.tasks.get_storage", return_value=storage):
        with pytest.raises(OSError):
            finalize_document.run(str(document.pk), str(document.operation_id))
    assert OSError in finalize_document.autoretry_for


@pytest.mark.django_db
def test_retry_exhaustion_records_sanitized_failure(editor_user):
    document = make_document(editor_user)
    document.status = DocumentStatus.PENDING
    document.processing_kind = ProcessingKind.CREATE
    document.operation_id = uuid.uuid4()
    document.save()
    finalize_document.on_failure(
        OSError("secret infrastructure detail"),
        "task-id",
        (str(document.pk), str(document.operation_id)),
        {},
        None,
    )
    document.refresh_from_db()
    assert document.status == DocumentStatus.FAILED
    assert document.processing_error == (
        "Storage operation failed after retry exhaustion."
    )
    assert "secret" not in document.processing_error
