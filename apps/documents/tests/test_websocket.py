import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator

from apps.documents.middleware import WebSocketTicketMiddleware
from apps.documents.routing import websocket_urlpatterns
from apps.documents.tickets import issue_ticket


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_valid_ticket_connects_once(editor_user):
    ticket = await issue_ticket_async(editor_user)
    app = WebSocketTicketMiddleware(URLRouter(websocket_urlpatterns))
    first = WebsocketCommunicator(app, f"/ws/notifications/?ticket={ticket}")
    connected, _ = await first.connect()
    assert connected
    await first.disconnect()
    replay = WebsocketCommunicator(app, f"/ws/notifications/?ticket={ticket}")
    connected, code = await replay.connect()
    assert not connected
    assert code == 4401


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_invalid_ticket_rejected():
    app = WebSocketTicketMiddleware(URLRouter(websocket_urlpatterns))
    communicator = WebsocketCommunicator(app, "/ws/notifications/?ticket=invalid")
    connected, code = await communicator.connect()
    assert not connected
    assert code == 4401


async def issue_ticket_async(user):
    from asgiref.sync import sync_to_async

    return await sync_to_async(issue_ticket)(user)
