from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import Department, Direction, OrgChartNode, Position


@admin.register(Direction)
class DirectionAdmin(TenantAwareAdmin):
    list_display = ("name", "code", "organization", "subsidiary", "head", "color")
    list_filter = ("organization", "subsidiary")
    search_fields = ("name", "code")
    autocomplete_fields = ("organization", "subsidiary", "head")


@admin.register(Department)
class DepartmentAdmin(TenantAwareAdmin):
    list_display = ("name", "direction", "head")
    list_filter = ("direction",)
    search_fields = ("name",)
    autocomplete_fields = ("direction", "head")


@admin.register(Position)
class PositionAdmin(TenantAwareAdmin):
    list_display = ("title", "department", "level", "holder", "is_executive_committee_member")
    list_filter = ("level", "is_executive_committee_member", "department")
    search_fields = ("title",)
    autocomplete_fields = ("department", "holder")


@admin.register(OrgChartNode)
class OrgChartNodeAdmin(TenantAwareAdmin):
    list_display = ("target_type", "target_id", "parent", "order", "collapsed")
    list_filter = ("target_type", "collapsed")
