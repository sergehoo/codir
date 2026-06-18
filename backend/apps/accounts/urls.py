from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView, LoginView, MembershipViewSet, MeView,
    MFADisableView, MFALoginVerifyView, MFASetupView, MFAVerifySetupView,
    MyMembershipsView, RoleViewSet, SwitchOrganizationView, UserViewSet,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"memberships", MembershipViewSet, basename="membership")

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("my-memberships/", MyMembershipsView.as_view(), name="auth-my-memberships"),
    path("switch-organization/", SwitchOrganizationView.as_view(), name="auth-switch-org"),
    # MFA TOTP
    path("mfa/setup/", MFASetupView.as_view(), name="auth-mfa-setup"),
    path("mfa/verify-setup/", MFAVerifySetupView.as_view(), name="auth-mfa-verify-setup"),
    path("mfa/verify/", MFALoginVerifyView.as_view(), name="auth-mfa-verify"),
    path("mfa/disable/", MFADisableView.as_view(), name="auth-mfa-disable"),
    path("", include(router.urls)),
]
