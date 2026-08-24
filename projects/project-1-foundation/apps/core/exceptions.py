from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        custom_data = {
            'type': 'about:blank',
            'title': exc.__class__.__name__,
            'status': response.status_code,
            'detail': response.data,
        }
        response.data = custom_data
    return response
