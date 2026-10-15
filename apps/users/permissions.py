from rest_framework.permissions import BasePermission

from .roles import is_admin


class IsDMSAdmin(BasePermission):
    message = "Administrator role is required."

    def has_permission(self, request, view):
        return is_admin(request.user)
