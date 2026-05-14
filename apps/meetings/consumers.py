"""WebSocket consumer pour le mode réunion live."""
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class MeetingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        org = self.scope.get("organization")
        if not user or not user.is_authenticated or org is None:
            return await self.close(code=4001)
        self.meeting_id = self.scope["url_route"]["kwargs"]["meeting_id"]
        if not await self._can_join(user.id, org.id, self.meeting_id):
            return await self.close(code=4003)
        self.group = f"org.{org.id}.meeting.{self.meeting_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self._broadcast({"type": "presence", "payload": {"user_id": str(user.id), "joined": True}})

    async def disconnect(self, code):
        if hasattr(self, "group"):
            user = self.scope.get("user")
            if user and user.is_authenticated:
                await self._broadcast({"type": "presence", "payload": {"user_id": str(user.id), "joined": False}})
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content):
        kind = content.get("type")
        # Dispatch minimal — l'écriture en DB doit passer par les services
        if kind == "presence.heartbeat":
            await self.send_json({"type": "presence.heartbeat.ack"})
        # vote.cast / note.update / hand.raise / ... à implémenter
        # → services/cast_vote / append_note / etc.

    async def meeting_event(self, event):
        await self.send_json(event["data"])

    async def _broadcast(self, data):
        await self.channel_layer.group_send(self.group, {"type": "meeting.event", "data": data})

    @database_sync_to_async
    def _can_join(self, user_id, org_id, meeting_id):
        from apps.meetings.models import Participation
        return Participation.unscoped.filter(
            meeting_id=meeting_id, user_id=user_id, organization_id=org_id,
        ).exists()
