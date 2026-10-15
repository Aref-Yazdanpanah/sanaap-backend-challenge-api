from unittest.mock import Mock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.audit.models import AuditAction, DocumentAuditLog
from apps.documents.models import Document, DocumentStatus


def make_document(owner, title="doc", status=DocumentStatus.READY):
    return Document.objects.create(
        title=title,
        owner=owner,
        original_filename="a.pdf",
        object_key=f"documents/{owner.pk}/{title}",
        content_type="application/pdf",
        size_bytes=10,
        checksum_sha256="a" * 64,
        status=status,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [("admin_user", 2), ("viewer_user", 2), ("editor_user", 1)],
)
def test_document_list_rbac(
    request, api_client, fixture_name, expected, editor_user, editor_two
):
    make_document(editor_user, "one")
    make_document(editor_two, "two")
    api_client.force_authenticate(request.getfixturevalue(fixture_name))
    response = api_client.get(reverse("document-list"))
    assert response.status_code == 200
    assert response.data["count"] == expected


@pytest.mark.django_db
def test_editor_cannot_retrieve_other_document(api_client, editor_user, editor_two):
    other = make_document(editor_two)
    api_client.force_authenticate(editor_user)
    assert (
        api_client.get(reverse("document-detail", args=[other.pk])).status_code == 404
    )


@pytest.mark.django_db
@pytest.mark.parametrize("fixture_name", ["editor_user", "viewer_user"])
def test_only_admin_deletes(request, api_client, fixture_name, editor_user):
    doc = make_document(editor_user)
    api_client.force_authenticate(request.getfixturevalue(fixture_name))
    expected = 403 if fixture_name == "viewer_user" else 403
    assert (
        api_client.delete(reverse("document-detail", args=[doc.pk])).status_code
        == expected
    )


@pytest.mark.django_db
def test_viewer_cannot_create(api_client, viewer_user):
    api_client.force_authenticate(viewer_user)
    assert api_client.post(reverse("document-list"), {"title": "x"}).status_code == 403


@pytest.mark.django_db
def test_owner_field_is_rejected(api_client, editor_user):
    api_client.force_authenticate(editor_user)
    upload = SimpleUploadedFile("ok.pdf", b"%PDF-1.4\n%%EOF")
    response = api_client.post(
        reverse("document-list"),
        {"title": "x", "owner": 999, "file": upload},
        format="multipart",
    )
    assert response.status_code == 400
    assert "owner" in response.data


@pytest.mark.django_db
def test_retrieve_is_audited(api_client, editor_user):
    doc = make_document(editor_user)
    api_client.force_authenticate(editor_user)
    assert api_client.get(reverse("document-detail", args=[doc.pk])).status_code == 200
    assert DocumentAuditLog.objects.filter(
        document=doc, action=AuditAction.RETRIEVE
    ).exists()


@pytest.mark.django_db
def test_ready_download_returns_ttl_and_audits(api_client, editor_user, settings):
    doc = make_document(editor_user)
    api_client.force_authenticate(editor_user)
    settings.DOCUMENT_PRESIGNED_URL_TTL = 60
    storage = Mock()
    storage.presigned_download.return_value = "http://storage.local/signed"
    with patch("apps.documents.views.get_storage", return_value=storage):
        response = api_client.get(reverse("document-download", args=[doc.pk]))
    assert response.status_code == 200
    assert response.data["expires_in"] == 60
    assert DocumentAuditLog.objects.filter(
        document=doc, action=AuditAction.DOWNLOAD_LINK_ISSUED
    ).exists()


@pytest.mark.django_db
def test_non_ready_download_conflicts(api_client, editor_user):
    doc = make_document(editor_user, status=DocumentStatus.PENDING)
    doc.object_key = None
    doc.save()
    api_client.force_authenticate(editor_user)
    assert (
        api_client.get(reverse("document-download", args=[doc.pk])).status_code == 409
    )


@pytest.mark.django_db
def test_filter_and_pagination(api_client, viewer_user, editor_user, settings):
    settings.REST_FRAMEWORK["PAGE_SIZE"] = 1
    make_document(editor_user, "needle")
    make_document(editor_user, "other")
    api_client.force_authenticate(viewer_user)
    response = api_client.get(
        reverse("document-list"), {"title": "needle", "page_size": 1}
    )
    assert response.status_code == 200
    assert response.data["count"] == 1
