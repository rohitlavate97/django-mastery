import uuid
from django.utils.deprecation import MiddlewareMixin

class CorrelationIdMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    
    def process_response(self, request, response):
        if hasattr(request, 'correlation_id'):
            response['X-Request-ID'] = request.correlation_id
        return response
