from rest_framework.permissions import BasePermission

from apps.users.roles import ADMIN, EDITOR, VIEWER, get_role_name


class DocumentPermission(BasePermission):
    message = "Your role does not permit this document operation."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        role = get_role_name(request.user)
        if view.action in ("list", "retrieve", "download"):
            return role in (ADMIN, EDITOR, VIEWER)
        if view.action == "create":
            return role in (ADMIN, EDITOR)
        if view.action in ("update", "partial_update"):
            return role in (ADMIN, EDITOR)
        if view.action == "destroy":
            return role == ADMIN
        return False

    def has_object_permission(self, request, view, obj):
        role = get_role_name(request.user)
        if role == ADMIN:
            return True
        if role == VIEWER:
            return view.action in ("retrieve", "download")
        if role == EDITOR:
            return obj.owner_id == request.user.id and view.action in (
                "retrieve",
                "download",
                "update",
                "partial_update",
            )
        return False
