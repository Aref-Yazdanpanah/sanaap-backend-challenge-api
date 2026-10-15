from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from .roles import assign_role

User = get_user_model()


def profile_cache_key(user_id) -> str:
    return f"user-profile:{user_id}"


@transaction.atomic
def create_user(
    *,
    username: str,
    password: str,
    role: str,
    first_name: str = "",
    last_name: str = "",
):
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    assign_role(user, role)
    return user


@transaction.atomic
def change_role(*, user, role: str):
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    assign_role(locked_user, role)
    transaction.on_commit(lambda: cache.delete(profile_cache_key(locked_user.pk)))
    return locked_user
