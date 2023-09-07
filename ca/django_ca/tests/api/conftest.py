# This file is part of django-ca (https://github.com/mathiasertl/django-ca).
#
# django-ca is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# django-ca is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along with django-ca. If not, see
# <http://www.gnu.org/licenses/>.
#
# pylint: disable=redefined-outer-name  # requested pytest fixtures show up this way.

"""pytest configuration for API tests."""
import base64
from typing import Any, Dict, List, Optional, Tuple, Type

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.test.client import Client

import pytest

from django_ca.models import Certificate, CertificateAuthority
from django_ca.tests.base.typehints import HttpResponse, User
from django_ca.tests.base.utils import iso_format

DetailResponse = Dict[str, Any]
ListResponse = List[DetailResponse]


@pytest.fixture()
def api_user(user: User, api_permission: Tuple[Type[Model], str]) -> User:
    """Extend user fixture to add required permission."""
    content_type = ContentType.objects.get_for_model(api_permission[0])
    permission = Permission.objects.get(codename=api_permission[1], content_type=content_type)
    user.user_permissions.add(permission)
    return user


@pytest.fixture()
def api_client(client: Client, api_user: User) -> Client:
    """HTTP client with HTTP basic authentication for the user."""
    credentials = base64.b64encode(api_user.username.encode("utf-8") + b":password").decode()
    client.defaults["HTTP_AUTHORIZATION"] = "Basic " + credentials
    return client


@pytest.fixture
def root_response(root: CertificateAuthority) -> DetailResponse:
    """Fixture for the expected response schema for the root CA."""
    return {
        "acme_enabled": False,
        "acme_profile": "webserver",
        "acme_registration": True,
        "acme_requires_contact": True,
        "caa_identity": "",
        "can_sign_certificates": False,
        "created": iso_format(root.created),
        "crl_url": root.crl_url,
        "issuer": [{"oid": attr.oid.dotted_string, "value": attr.value} for attr in root.issuer],
        "issuer_alt_name": "",
        "issuer_url": root.issuer_url,
        "not_after": iso_format(root.expires),
        "not_before": iso_format(root.valid_from),
        "ocsp_responder_key_validity": 3,
        "ocsp_response_validity": 86400,
        "ocsp_url": root.ocsp_url,
        "name": "root",
        "pem": root.pub.pem,
        "revoked": False,
        "serial": root.serial,
        "sign_certificate_policies": None,
        "subject": [{"oid": attr.oid.dotted_string, "value": attr.value} for attr in root.subject],
        "terms_of_service": "",
        "updated": iso_format(root.updated),
        "website": "",
    }


@pytest.fixture()
def root_cert_response(root_cert: Certificate) -> DetailResponse:
    """Fixture for the expected response schema for the certificate signed by the root CA."""
    return {
        "autogenerated": False,
        "created": iso_format(root_cert.created),
        "issuer": [{"oid": attr.oid.dotted_string, "value": attr.value} for attr in root_cert.issuer],
        "not_after": iso_format(root_cert.expires),
        "not_before": iso_format(root_cert.valid_from),
        "pem": root_cert.pub.pem,
        "profile": root_cert.profile,
        "revoked": False,
        "serial": root_cert.serial,
        "subject": [{"oid": attr.oid.dotted_string, "value": attr.value} for attr in root_cert.subject],
        "updated": iso_format(root_cert.updated),
    }
