import pytest
import jwt
from django.conf import settings
from channels.testing import WebsocketCommunicator
from config.asgi import application
from apps.notifications.services import send_tenant_notification

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_connection_and_notification(tenant, user):
    # Generate JWT token
    token = jwt.encode({"user_id": user.id}, settings.SECRET_KEY, algorithm="HS256")
    
    # Connect
    communicator = WebsocketCommunicator(
        application, 
        f"/ws/notifications/{tenant.id}/?token={token}"
    )
    connected, subprotocol = await communicator.connect()
    assert connected
    
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    group_name = f"tenant_{tenant.id}_user_{user.id}"
    
    await channel_layer.group_send(
        group_name,
        {
            "type": "tenant_message",
            "message": "Hello from backend!"
        }
    )
    
    # Receive
    response = await communicator.receive_json_from()
    assert response["message"] == "Hello from backend!"
    
    await communicator.disconnect()
