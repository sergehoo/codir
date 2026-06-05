"""Views audit_logs : 2 endpoints admin-only.

- AuditLogViewSet : journal d'activité applicative (CRUD métier, login/logout, admin)
- AccessLogListView : connexions/échecs depuis django-axes (AccessLog + AccessAttempt)
"""
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination

from .models import AuditLog
from .permissions import IsOrganizationAdmin
from .serializers import AccessLogSerializer, AuditLogSerializer


class _AdminPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "limit"
    max_page_size = 200


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Logs applicatifs (CRUD métier + auth + admin) scopés sur l'organisation."""

    permission_classes = [IsOrganizationAdmin]
    serializer_class = AuditLogSerializer
    pagination_class = _AdminPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["action", "actor"]
    search_fields = ["description", "target_repr", "actor__email", "actor__first_name", "actor__last_name"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        qs = AuditLog.unscoped.select_related("actor", "target_type")
        if org is not None:
            qs = qs.filter(organization=org)
        # Filtres date (ISO date "YYYY-MM-DD")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs


class AccessLogListView(ListAPIView):
    """Logs de connexion (succès + échecs) issus de django-axes.

    Source :
      - axes.AccessLog       → connexions réussies (avec logout_time éventuel)
      - axes.AccessAttempt   → tentatives bloquées / échecs

    Scope : usernames (= emails) des memberships actifs de l'organisation.
    """

    permission_classes = [IsOrganizationAdmin]
    serializer_class = AccessLogSerializer
    pagination_class = _AdminPagination

    def get_queryset(self):
        # Cette méthode est requise par ListAPIView mais on construit la liste
        # à la main dans list() pour fusionner deux modèles.
        return []

    def _org_user_map(self):
        """Retourne {email_lower: User} pour les membres actifs du tenant."""
        from apps.accounts.models import Membership
        org = getattr(self.request, "organization", None)
        if org is None:
            return {}
        rows = (
            Membership.unscoped
            .filter(organization=org, is_active=True)
            .select_related("user")
        )
        out = {}
        for m in rows:
            email = (m.user.email or "").strip().lower()
            if email:
                out[email] = m.user
        return out

    def list(self, request, *args, **kwargs):
        from axes.models import AccessAttempt, AccessLog
        from rest_framework.response import Response

        user_map = self._org_user_map()
        emails = list(user_map.keys())
        kind_filter = (request.query_params.get("kind") or "").lower()
        username_filter = (request.query_params.get("username") or "").strip().lower()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        rows: list[dict] = []

        # ── 1. Succès (AccessLog) ────────────────────────────
        if kind_filter in ("", "success"):
            qs_ok = AccessLog.objects.all()
            if emails:
                qs_ok = qs_ok.filter(username__in=emails)
            if username_filter:
                qs_ok = qs_ok.filter(username__iexact=username_filter)
            if date_from:
                qs_ok = qs_ok.filter(attempt_time__date__gte=date_from)
            if date_to:
                qs_ok = qs_ok.filter(attempt_time__date__lte=date_to)
            for r in qs_ok.order_by("-attempt_time")[:500]:
                u = user_map.get((r.username or "").strip().lower())
                rows.append({
                    "kind": "success",
                    "username": r.username,
                    "user_id": u.id if u else None,
                    "user_full_name": (u.get_full_name() if u else "") or "",
                    "ip_address": r.ip_address,
                    "user_agent": (r.user_agent or "")[:500],
                    "path_info": r.path_info or "",
                    "attempt_time": r.attempt_time,
                    "logout_time": r.logout_time,
                    "failures_since_start": None,
                })

        # ── 2. Échecs (AccessAttempt) ────────────────────────
        if kind_filter in ("", "failed"):
            qs_ko = AccessAttempt.objects.all()
            # Note : on ne filtre PAS par emails ici car on veut aussi voir les
            # tentatives sur des emails inconnus (= bruteforce). On laisse l'admin
            # voir TOUTES les tentatives qui visent son tenant (par défaut tous
            # les axes-events sont visibles aux admins).
            if username_filter:
                qs_ko = qs_ko.filter(username__iexact=username_filter)
            if date_from:
                qs_ko = qs_ko.filter(attempt_time__date__gte=date_from)
            if date_to:
                qs_ko = qs_ko.filter(attempt_time__date__lte=date_to)
            for r in qs_ko.order_by("-attempt_time")[:500]:
                u = user_map.get((r.username or "").strip().lower())
                rows.append({
                    "kind": "failed",
                    "username": r.username,
                    "user_id": u.id if u else None,
                    "user_full_name": (u.get_full_name() if u else "") or "",
                    "ip_address": r.ip_address,
                    "user_agent": (r.user_agent or "")[:500],
                    "path_info": r.path_info or "",
                    "attempt_time": r.attempt_time,
                    "logout_time": None,
                    "failures_since_start": r.failures_since_start,
                })

        # ── 3. Tri + pagination manuelle ─────────────────────
        rows.sort(key=lambda x: x["attempt_time"], reverse=True)
        page = self.paginate_queryset(rows)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(rows, many=True).data)
