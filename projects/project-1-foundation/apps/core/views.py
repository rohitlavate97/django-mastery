from django.http import JsonResponse
from django.db import connection

def health_check(request):
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    
    return JsonResponse({'status': 'ok' if db_ok else 'error', 'db': db_ok})
