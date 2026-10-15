from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .events import NOTIFICATION_GROUP


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if not self.scope["user"].is_authenticated or not self.scope["user"].is_active:
            await self.close(code=4401)
            return
        await self.channel_layer.group_add(NOTIFICATION_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if getattr(self, "channel_name", None):
            await self.channel_layer.group_discard(
                NOTIFICATION_GROUP, self.channel_name
            )

    async def document_notification(self, event):
        await self.send_json({"event": event["event"], "message": event["message"]})
