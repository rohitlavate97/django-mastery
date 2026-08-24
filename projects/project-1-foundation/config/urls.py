from django.urls import path, include
from apps.core.views import health_check

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('api/v1/auth/', include('apps.users.urls')),
]
