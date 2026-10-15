import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_login_refresh_logout(api_client, editor_user):
    login = api_client.post(
        reverse("token-obtain"),
        {"username": "editor", "password": "StrongPassword!123"},
    )
    assert login.status_code == 200
    refresh = login.data["refresh"]
    refreshed = api_client.post(reverse("token-refresh"), {"refresh": refresh})
    assert refreshed.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    assert (
        api_client.post(
            reverse("logout"), {"refresh": refreshed.data["refresh"]}
        ).status_code
        == 204
    )


@pytest.mark.django_db
def test_bad_login(api_client, editor_user):
    assert (
        api_client.post(
            reverse("token-obtain"), {"username": "editor", "password": "wrong"}
        ).status_code
        == 401
    )


@pytest.mark.django_db
def test_inactive_login_rejected(api_client, editor_user):
    editor_user.is_active = False
    editor_user.save()
    assert (
        api_client.post(
            reverse("token-obtain"),
            {"username": "editor", "password": "StrongPassword!123"},
        ).status_code
        == 401
    )


@pytest.mark.django_db
def test_me_is_cached_per_user(api_client, editor_user):
    api_client.force_authenticate(editor_user)
    first = api_client.get(reverse("user-me"))
    second = api_client.get(reverse("user-me"))
    assert first.status_code == second.status_code == 200
    assert first.data["username"] == "editor"


@pytest.mark.django_db
def test_admin_creates_user_and_assigns_role(api_client, admin_user):
    api_client.force_authenticate(admin_user)
    response = api_client.post(
        reverse("user-list"),
        {"username": "new", "password": "A-Very-Strong-Password!42", "role": "Viewer"},
    )
    assert response.status_code == 201
    assert response.data["role"] == "Viewer"
    assert "password" not in response.data


@pytest.mark.django_db
@pytest.mark.parametrize("fixture_name", ["editor_user", "viewer_user"])
def test_non_admin_cannot_manage_users(request, api_client, fixture_name):
    api_client.force_authenticate(request.getfixturevalue(fixture_name))
    assert api_client.get(reverse("user-list")).status_code == 403


@pytest.mark.django_db
def test_admin_changes_role(api_client, admin_user, editor_user):
    api_client.force_authenticate(admin_user)
    response = api_client.patch(
        reverse("user-set-role", args=[editor_user.pk]), {"role": "Viewer"}
    )
    assert response.status_code == 200
    assert response.data["role"] == "Viewer"
