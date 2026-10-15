import pytest

from apps.documents.models import Document, DocumentStatus
from apps.documents.selectors import document_queryset_for_user


def document(owner, title):
    return Document.objects.create(
        title=title,
        owner=owner,
        original_filename="a.pdf",
        object_key=f"documents/{title}",
        content_type="application/pdf",
        size_bytes=1,
        checksum_sha256="a" * 64,
        status=DocumentStatus.READY,
    )


@pytest.mark.django_db
def test_editor_queryset_is_owner_scoped(editor_user, editor_two):
    own = document(editor_user, "own")
    document(editor_two, "other")
    assert list(document_queryset_for_user(editor_user)) == [own]


@pytest.mark.django_db
@pytest.mark.parametrize("fixture_name", ["admin_user", "viewer_user"])
def test_admin_and_viewer_see_all(request, fixture_name, editor_user, editor_two):
    user = request.getfixturevalue(fixture_name)
    document(editor_user, "one")
    document(editor_two, "two")
    assert document_queryset_for_user(user).count() == 2
