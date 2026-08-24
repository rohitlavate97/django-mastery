from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from .models import WebhookEvent
from .tasks import process_webhook_event

class WebhookIngestView(APIView):
    def post(self, request):
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response({"error": "Idempotency-Key header missing"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            event = WebhookEvent.objects.create(
                idempotency_key=idempotency_key,
                payload=request.data
            )
            process_webhook_event.delay(event.id)
            return Response({"status": "accepted"}, status=status.HTTP_202_ACCEPTED)
        except IntegrityError:
            # Idempotency key already exists
            return Response({"status": "already_processed"}, status=status.HTTP_200_OK)
