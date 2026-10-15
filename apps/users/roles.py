from django.contrib.auth.models import Group

ADMIN = "Admin"
EDITOR = "Editor"
VIEWER = "Viewer"
ROLE_NAMES = (ADMIN, EDITOR, VIEWER)


def get_role_name(user) -> str | None:
    if user.is_superuser:
        return ADMIN
    return (
        user.groups.filter(name__in=ROLE_NAMES).values_list("name", flat=True).first()
    )


def is_admin(user) -> bool:
    return bool(
        user.is_authenticated
        and (user.is_superuser or user.groups.filter(name=ADMIN).exists())
    )


def assign_role(user, role: str) -> None:
    role_group = Group.objects.get(name=role)
    user.groups.remove(*Group.objects.filter(name__in=ROLE_NAMES))
    user.groups.add(role_group)
