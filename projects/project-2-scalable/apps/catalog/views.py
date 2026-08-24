from rest_framework.views import APIView
from rest_framework.response import Response
from .services import CatalogService

class ProductDetailView(APIView):
    def get(self, request, pk):
        data = CatalogService.get_product_details(pk)
        return Response(data)
