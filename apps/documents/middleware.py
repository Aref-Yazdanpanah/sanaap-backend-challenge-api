from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from .tickets import consume_ticket


@database_sync_to_async
def user_for_ticket(ticket):
    data = consume_ticket(ticket)
    if not data:
        return AnonymousUser()
    return (
        get_user_model().objects.filter(pk=data["user_id"], is_active=True).first()
        or AnonymousUser()
    )


class WebSocketTicketMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        params = parse_qs(scope.get("query_string", b"").decode())
        ticket = params.get("ticket", [""])[0]
        scope["user"] = await user_for_ticket(ticket) if ticket else AnonymousUser()
        return await self.app(scope, receive, send)
