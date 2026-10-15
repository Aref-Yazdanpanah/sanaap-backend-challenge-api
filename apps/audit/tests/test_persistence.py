import pytest

from apps.audit.models import AuditAction
from apps.audit.services import record_document_audit
from apps.documents.tests.test_api import make_document


@pytest.mark.django_db
def test_audit_snapshot_survives_document_delete(editor_user):
    doc = make_document(editor_user)
    audit = record_document_audit(
        document=doc, actor=editor_user, action=AuditAction.DELETE
    )
    doc_id = doc.pk
    doc.delete()
    audit.refresh_from_db()
    assert audit.document is None
    assert audit.document_id_snapshot == doc_id
    assert audit.actor_username_snapshot == "editor"
