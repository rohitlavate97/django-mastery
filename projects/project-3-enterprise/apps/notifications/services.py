from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_tenant_notification(tenant_id, user_id, message):
    channel_layer = get_channel_layer()
    group_name = f"tenant_{tenant_id}_user_{user_id}"
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "tenant_message",
            "message": message,
        }
    )
