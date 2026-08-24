from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import PlaceOrderSerializer
from .services import OrderService
from .tasks import send_order_confirmation_email

class PlaceOrderView(APIView):
    def post(self, request):
        serializer = PlaceOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = OrderService.place_order(
                product_id=serializer.validated_data['product_id'],
                quantity=serializer.validated_data['quantity']
            )
            
            # Async task
            send_order_confirmation_email.delay(order.id)
            
            return Response({"order_id": order.id, "status": order.status}, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
