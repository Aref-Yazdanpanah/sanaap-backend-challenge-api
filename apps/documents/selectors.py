from apps.users.roles import ADMIN, EDITOR, VIEWER, get_role_name

from .models import Document


def document_queryset_for_user(user):
    queryset = Document.objects.select_related("owner")
    role = get_role_name(user)
    if role in (ADMIN, VIEWER):
        return queryset
    if role == EDITOR:
        return queryset.filter(owner=user)
    return queryset.none()
