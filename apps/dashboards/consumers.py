"""WebSocket consumer pour le live des dashboards."""
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class DashboardConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        org = self.scope.get("organization")
        if not user or not user.is_authenticated or org is None:
            return await self.close(code=4001)
        self.dashboard_id = self.scope["url_route"]["kwargs"]["dashboard_id"]
        self.group = f"org.{org.id}.dashboard.{self.dashboard_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def dashboard_event(self, event):
        await self.send_json(event["data"])
