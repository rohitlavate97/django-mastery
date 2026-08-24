from django.urls import path, include
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path('health/', health_check),
    path('', include('django_prometheus.urls')),
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/orders/', include('apps.orders.urls')),
    path('api/v1/webhooks/', include('apps.webhooks.urls')),
]
