from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardCursorPagination(CursorPagination):
    page_size = 25
    page_size_query_param = "limit"
    max_page_size = 200
    ordering = "-created_at"


class SmallPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "limit"
    max_page_size = 100
