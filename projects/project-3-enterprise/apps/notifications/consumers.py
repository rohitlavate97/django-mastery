import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TenantNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        # Get tenant_id from URL route kwargs
        self.tenant_id = self.scope['url_route']['kwargs'].get('tenant_id')
        
        if self.user.is_anonymous or not self.tenant_id:
            await self.close()
            return
            
        # Group name specific to tenant and user
        self.group_name = f"tenant_{self.tenant_id}_user_{self.user.id}"
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        pass

    async def tenant_message(self, event):
        message = event["message"]

        await self.send(text_data=json.dumps({
            "message": message
        }))
