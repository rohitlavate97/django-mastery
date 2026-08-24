from rest_framework.pagination import PageNumberPagination, CursorPagination

class StandardPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class StandardCursorPagination(CursorPagination):
    page_size = 20
    ordering = '-created_at'
