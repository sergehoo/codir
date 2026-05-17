"""
Pagination DRF standard pour CODIR.

`PageNumberPagination` (et non `CursorPagination` par défaut DRF) car :
  - Compatible avec ``?page=N&page_size=M`` que le frontend React utilise déjà
  - Pas de prérequis sur le champ ``created`` (CursorPagination y est lié)
  - Retourne ``count`` total et liens next/previous, utile pour le SPA
"""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Pagination standard avec `page_size` configurable par le client.

    Réponse:
        {
            "count": 42,
            "next": "https://.../?page=2",
            "previous": null,
            "results": [...]
        }
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500
