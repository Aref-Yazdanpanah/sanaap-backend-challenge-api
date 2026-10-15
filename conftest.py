import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.users.roles import ADMIN, EDITOR, VIEWER


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def roles(db):
    return {name: Group.objects.create(name=name) for name in (ADMIN, EDITOR, VIEWER)}


@pytest.fixture
def user_factory(db, roles):
    def factory(username, role, password="StrongPassword!123", **kwargs):
        user = get_user_model().objects.create_user(
            username=username, password=password, **kwargs
        )
        user.groups.add(roles[role])
        return user

    return factory


@pytest.fixture
def admin_user(user_factory):
    return user_factory("admin", ADMIN)


@pytest.fixture
def editor_user(user_factory):
    return user_factory("editor", EDITOR)


@pytest.fixture
def editor_two(user_factory):
    return user_factory("editor2", EDITOR)


@pytest.fixture
def viewer_user(user_factory):
    return user_factory("viewer", VIEWER)
