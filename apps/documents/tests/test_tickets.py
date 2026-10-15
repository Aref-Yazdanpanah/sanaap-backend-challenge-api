import pytest

from apps.documents.tickets import consume_ticket, issue_ticket


@pytest.mark.django_db
def test_ticket_is_opaque_and_one_time(editor_user):
    ticket = issue_ticket(editor_user)
    assert str(editor_user.pk) not in ticket
    assert consume_ticket(ticket)["user_id"] == editor_user.pk
    assert consume_ticket(ticket) is None
