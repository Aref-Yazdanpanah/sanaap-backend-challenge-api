from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

NOTIFICATION_GROUP = "authenticated_documents"


def publish_document_event(event: str) -> None:
    messages = {
        "document_created": "A new document has been uploaded.",
        "document_updated": "A document has been updated.",
    }
    async_to_sync(get_channel_layer().group_send)(
        NOTIFICATION_GROUP,
        {"type": "document.notification", "event": event, "message": messages[event]},
    )
