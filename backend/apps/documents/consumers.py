"""WebSocket consumer pour l'édition collaborative documents (relais Yjs)."""
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class DocumentPresenceConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        org = self.scope.get("organization")
        if not user or not user.is_authenticated or org is None:
            return await self.close(code=4001)
        self.document_id = self.scope["url_route"]["kwargs"]["document_id"]
        self.group = f"org.{org.id}.document.{self.document_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content):
        # Relai pur des messages Yjs aux autres participants
        await self.channel_layer.group_send(self.group, {"type": "doc.event", "data": content, "sender": self.channel_name})

    async def doc_event(self, event):
        if event.get("sender") == self.channel_name:
            return  # ne renvoie pas à l'émetteur
        await self.send_json(event["data"])
