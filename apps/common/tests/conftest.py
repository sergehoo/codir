"""Fixtures pytest partagées bêta."""
import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Membership, Role
from apps.organizations.models import Organization
from core.managers.tenant import current_organization

User = get_user_model()


@pytest.fixture
def org(db):
    o = Organization.unscoped.create(name="Acme", slug="acme", country="FR", timezone="Europe/Paris")
    token = current_organization.set(o)
    yield o
    current_organization.reset(token)


@pytest.fixture
def role_owner(db, org):
    return Role.unscoped.create(organization=org, code="OWNER", name="Owner", is_system=True)


@pytest.fixture
def user(db, org, role_owner):
    u = User.objects.create_user(email="dg@acme.local", password="pwd", first_name="C", last_name="M", is_executive=True)
    m = Membership.unscoped.create(organization=org, user=u, is_owner=True, is_executive=True, is_active=True)
    m.roles.add(role_owner)
    return u


@pytest.fixture
def api_client(user):
    from rest_framework.test import APIClient
    c = APIClient()
    c.force_authenticate(user=user)
    return c
