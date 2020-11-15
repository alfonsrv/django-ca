# This file is part of django-ca (https://github.com/mathiasertl/django-ca).
#
# django-ca is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# django-ca is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with django-ca.  If not,
# see <http://www.gnu.org/licenses/>.

"""Test ACME related views."""

import json
import os
from datetime import datetime
from http import HTTPStatus
from unittest import mock

from requests.utils import parse_header_links

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from freezegun import freeze_time

from .. import ca_settings
from ..models import AcmeAccount
from ..models import AcmeAccountAuthorization
from ..models import AcmeCertificate
from ..models import AcmeChallenge
from ..models import AcmeOrder
from ..models import CertificateAuthority
from .base import DjangoCAWithCATestCase
from .base import DjangoCAWithCertTestCase
from .base import override_settings
from .base import timestamps

with open(os.path.join(settings.FIXTURES_DIR, 'prepared-acme-requests.json')) as stream:
    prepared_requests = json.load(stream)

PEM_1 = '''-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw3q0fOrSzCDmVVwGZ6Hi
10PUzj50zNSK1cyK9wjwq8LY1IKPmqKDP3p+BD3ko1rPu9Tx/2GlcgzntsEuphkX
sE8ssLesN3gN3LmR3QUMK1X9EopYOisSHfHvGFJtWKhmauWw0KcRl0bTwzLuVqmP
IO+Ev/pjgoZxD+jYzijQ+pkWmb0d5DBY4mtaQoCE3Lnwvljytip7nx58fh+D7TuK
k71Op5ZvDfyewE0oicZzAJ1cjCkBMGUPxPJO+YgQGWtkEldQKc7KXZpEe91wa9pF
YNINZMWl2MfVNLQKRwPoctvskjB79YuC/fBUwhd0AnKLX7JK23Spru0obzGUcdPE
xQIDAQAB
-----END PUBLIC KEY-----'''


class DirectoryTestCase(DjangoCAWithCATestCase):
    """Test basic ACMEv2 directory view."""
    url = reverse('django_ca:acme-directory')

    @freeze_time(timestamps['everything_valid'])
    def test_default(self):
        """Test the default directory view."""
        ca = CertificateAuthority.objects.default()
        ca.acme_enabled = True
        ca.save()

        with mock.patch('secrets.token_bytes', return_value=b'foobar'):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        req = response.wsgi_request
        self.assertEqual(response.json(), {
            'Zm9vYmFy': 'https://community.letsencrypt.org/t/adding-random-entries-to-the-directory/33417',
            'keyChange': 'http://localhost:8000/django_ca/acme/todo/key-change',
            'revokeCert': 'http://localhost:8000/django_ca/acme/todo/revoke-cert',
            'newAccount': req.build_absolute_uri('/django_ca/acme/%s/new-account/' % ca.serial),
            'newNonce': req.build_absolute_uri('/django_ca/acme/%s/new-nonce/' % ca.serial),
            'newOrder': req.build_absolute_uri('/django_ca/acme/%s/new-order/' % ca.serial),
        })

    @freeze_time(timestamps['everything_valid'])
    def test_named_ca(self):
        """Test getting directory for named CA."""

        ca = CertificateAuthority.objects.default()
        ca.acme_enabled = True
        ca.save()

        url = reverse('django_ca:acme-directory', kwargs={'serial': ca.serial})
        with mock.patch('secrets.token_bytes', return_value=b'foobar'):
            response = self.client.get(url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response['Content-Type'], 'application/json')
        req = response.wsgi_request
        self.assertEqual(response.json(), {
            'Zm9vYmFy': 'https://community.letsencrypt.org/t/adding-random-entries-to-the-directory/33417',
            'keyChange': 'http://localhost:8000/django_ca/acme/todo/key-change',
            'revokeCert': 'http://localhost:8000/django_ca/acme/todo/revoke-cert',
            'newAccount': req.build_absolute_uri('/django_ca/acme/%s/new-account/' % ca.serial),
            'newNonce': req.build_absolute_uri('/django_ca/acme/%s/new-nonce/' % ca.serial),
            'newOrder': req.build_absolute_uri('/django_ca/acme/%s/new-order/' % ca.serial),
        })

    @freeze_time(timestamps['everything_valid'])
    def test_meta(self):
        """Test the meta property."""
        ca = CertificateAuthority.objects.default()
        ca.acme_enabled = True
        ca.website = 'http://ca.example.com'
        ca.acme_terms_of_service = 'http://ca.example.com/acme/tos'
        ca.caa_identity = 'ca.example.com'
        ca.save()

        url = reverse('django_ca:acme-directory', kwargs={'serial': ca.serial})
        with mock.patch('secrets.token_bytes', return_value=b'foobar'):
            response = self.client.get(url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response['Content-Type'], 'application/json')
        req = response.wsgi_request
        self.assertEqual(response.json(), {
            'Zm9vYmFy': 'https://community.letsencrypt.org/t/adding-random-entries-to-the-directory/33417',
            'keyChange': 'http://localhost:8000/django_ca/acme/todo/key-change',
            'revokeCert': 'http://localhost:8000/django_ca/acme/todo/revoke-cert',
            'newAccount': req.build_absolute_uri('/django_ca/acme/%s/new-account/' % ca.serial),
            'newNonce': req.build_absolute_uri('/django_ca/acme/%s/new-nonce/' % ca.serial),
            'newOrder': req.build_absolute_uri('/django_ca/acme/%s/new-order/' % ca.serial),
            'meta': {
                'termsOfService': ca.acme_terms_of_service,
                'caaIdentities': [
                    ca.caa_identity,
                ],
                'website': ca.website,
            },
        })

    @freeze_time(timestamps['everything_valid'])
    def test_acme_default_disabled(self):
        """Test that fetching the default CA with ACME disabled doesn't work."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response['Content-Type'], 'application/problem+json')
        self.assertEqual(response.json(), {
            'detail': 'No (usable) default CA configured.',
            'status': 404,
            'type': 'urn:ietf:params:acme:error:not-found',
        })

    @freeze_time(timestamps['everything_valid'])
    def test_acme_disabled(self):
        """Test that fetching the default CA with ACME disabled doesn't work."""
        ca = CertificateAuthority.objects.default()
        url = reverse('django_ca:acme-directory', kwargs={'serial': ca.serial})
        response = self.client.get(url)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response['Content-Type'], 'application/problem+json')
        self.assertEqual(response.json(), {
            'detail': '%s: CA not found.' % ca.serial,
            'status': 404,
            'type': 'urn:ietf:params:acme:error:not-found',
        })

    def test_no_ca(self):
        """Test using default CA when **no** CA exists."""
        CertificateAuthority.objects.all().delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response['Content-Type'], 'application/problem+json')
        self.assertEqual(response.json(), {
            'detail': 'No (usable) default CA configured.',
            'status': 404,
            'type': 'urn:ietf:params:acme:error:not-found',
        })

    @freeze_time(timestamps['everything_expired'])
    def test_expired_ca(self):
        """Test using default CA when all CAs are expired."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response['Content-Type'], 'application/problem+json')
        self.assertEqual(response.json(), {
            'detail': 'No (usable) default CA configured.',
            'status': 404,
            'type': 'urn:ietf:params:acme:error:not-found',
        })

    @override_settings(CA_ENABLE_ACME=False)
    def test_disabled(self):
        """Test that CA_ENABLE_ACME=False means HTTP 404."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response['Content-Type'], 'text/html')  # --> coming from Django

    def test_unknown_serial(self):
        """Test explicitly naming an unknown serial."""
        serial = 'ABCDEF'
        url = reverse('django_ca:acme-directory', kwargs={'serial': serial})
        response = self.client.get(url)

        self.assertEqual(response['Content-Type'], 'application/problem+json')
        self.assertEqual(response.json(), {
            'detail': 'ABCDEF: CA not found.',
            'status': 404,
            'type': 'urn:ietf:params:acme:error:not-found',
        })


class AcmeTestCaseMixin:
    """TestCase mixin with various common utility functions."""

    def assertAcmeProblem(self, response, typ, status, ca=None):  # pylint: disable=invalid-name
        """Assert that a HTTP response confirms to an ACME problem report.

        .. seealso:: `RFC 8555, section 8 <https://tools.ietf.org/html/rfc8555#section-6.7>`_
        """
        self.assertEqual(response['Content-Type'], 'application/problem+json')
        self.assertLinkRelations(response, ca=ca)
        data = response.json()
        self.assertEqual(data['type'], 'urn:ietf:params:acme:error:%s' % typ)
        self.assertEqual(data['status'], status)
        self.assertIn('Replay-Nonce', response)

    def assertAcmeResponse(self, response, ca=None):  # pylint: disable=invalid-name
        """Assert basic Acme Response properties (Content-Type & Link header)."""
        self.assertLinkRelations(response, ca=ca)
        self.assertEqual(response['Content-Type'], 'application/json')

    def assertLinkRelations(self, response, ca=None, **kwargs):  # pylint: disable=invalid-name
        """Assert Link relations for a given request."""
        if ca is None:
            ca = self.ca

        directory = reverse('django_ca:acme-directory', kwargs={'serial': ca.serial})
        kwargs['index'] = response.wsgi_request.build_absolute_uri(directory)

        expected = [{'rel': k, 'url': v} for k, v in kwargs.items()]
        actual = parse_header_links(response['Link'])
        self.assertEqual(expected, actual)

    def post(self, url, data, **kwargs):
        """Make a post request with some ACME specific default data."""
        kwargs.setdefault('content_type', 'application/jose+json')
        kwargs.setdefault('SERVER_NAME', 'localhost:8000')
        return self.client.post(url, json.dumps(data), **kwargs)


class AcmeNewNonceViewTestCase(DjangoCAWithCATestCase):
    """Test getting a new ACME nonce."""

    def setUp(self):
        super().setUp()
        self.url = reverse('django_ca:acme-new-nonce', kwargs={'serial': self.cas['root'].serial})

    @override_settings(CA_ENABLE_ACME=False)
    def test_disabled(self):
        """Test that CA_ENABLE_ACME=False means HTTP 404."""
        response = self.client.head(self.url)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response['Content-Type'], 'text/html')  # --> coming from Django

    def test_get_nonce(self):
        """Test that getting multiple nonces returns unique nonces."""

        nonces = []
        for _i in range(1, 5):
            response = self.client.head(self.url)
            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertEqual(len(response['replay-nonce']), 43)
            self.assertEqual(response['cache-control'], 'no-store')
            nonces.append(response['replay-nonce'])

        self.assertEqual(len(nonces), len(set(nonces)))

    def test_get_request(self):
        """RFC 8555, section 7.2 also specifies a GET request."""

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertEqual(len(response['replay-nonce']), 43)
        self.assertEqual(response['cache-control'], 'no-store')


class AcmePreparedRequestsTestCaseMixin(AcmeTestCaseMixin):
    """Mixin for testing requests recorded from actual certbot sessions."""

    # The serial of the CA that was used when recording requests
    ca_serial = '3F1E6E9B3996B26B8072E4DD2597E8B40F3FBC7E'
    expected_status_code = HTTPStatus.OK

    def setUp(self):  # pylint: disable=invalid-name, missing-function-docstring; unittest standard
        super().setUp()
        self.ca = self.cas['root']
        self.ca.acme_enabled = True
        self.ca.serial = self.ca_serial
        self.ca.save()

    def before_prepared_request(self, data):
        """Any action to take **before** sending a prepared request."""

    def assertFailedPreparedResponse(self, data, response):  # pylint: disable=invalid-name
        """Any assertions after doing a prepared request while ACME is disabled."""

    def assertDuplicateNoncePreparedResponse(self, data, response):  # pylint: disable=invalid-name
        """Any assertions after doing a prepared request twice with the same nonce."""

    def assertPreparedResponse(self, data, response, celery_mock):  # pylint: disable=invalid-name
        """Any assertions on the response of a prepared request."""

    def get_url(self, data):  # pylint: disable=unused-argument
        """Get URL based on given request data."""
        return self.url

    @property
    def requests(self):
        """Get prepared requests for `self.view_name`."""
        return prepared_requests[self.view_name]

    def test_requests(self):
        """Test requests collected from certbot."""

        for data in self.requests:
            cache.set('acme-nonce-%s-%s' % (self.ca.serial, data['nonce']), 0)
            self.before_prepared_request(data)
            with self.mute_celery() as celery_mock:
                response = self.post(self.get_url(data), data['body'])
            self.assertEqual(response.status_code, self.expected_status_code)
            self.assertAcmeResponse(response)
            self.assertPreparedResponse(data, response, celery_mock)

    @override_settings(CA_ENABLE_ACME=False)
    def test_disabled(self):
        """Test that CA_ENABLE_ACME=False means HTTP 404."""
        for data in self.requests:
            cache.set('acme-nonce-%s-%s' % (self.ca.serial, data['nonce']), 0)
            self.before_prepared_request(data)
            response = self.post(self.get_url(data), data['body'])
            self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
            self.assertEqual(response['Content-Type'], 'text/html')  # --> coming from Django
            self.assertFailedPreparedResponse(data, response)

    def test_invalid_content_type(self):
        """Test sending an invalid content type."""
        for data in self.requests:
            cache.set('acme-nonce-%s-%s' % (self.ca.serial, data['nonce']), 0)
            self.before_prepared_request(data)
            response = self.post(self.get_url(data), data['body'], content_type='application/json')
            self.assertAcmeProblem(response, typ='malformed', status=415)
            self.assertFailedPreparedResponse(data, response)

    def test_duplicate_nonce_use(self):
        """Test that a Nonce can really only be used once."""
        for data in self.requests:
            cache.set('acme-nonce-%s-%s' % (self.ca.serial, data['nonce']), 0)
            self.before_prepared_request(data)
            with self.mute_celery() as celery_mock:
                response = self.post(self.get_url(data), data['body'])
            self.assertEqual(response.status_code, self.expected_status_code)
            self.assertAcmeResponse(response)
            self.assertPreparedResponse(data, response, celery_mock)

            # Do the request again to validate that the nonce is now invalid
            response = self.post(self.get_url(data), data['body'])
            self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
            self.assertAcmeProblem(response, typ='badNonce', status=400)
            self.assertDuplicateNoncePreparedResponse(data, response)

    def test_unknown_nonce_use(self):
        """Test that an unknown nonce does not work."""
        for data in self.requests:
            self.before_prepared_request(data)
            response = self.post(self.get_url(data), data['body'])
            self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
            self.assertAcmeProblem(response, typ='badNonce', status=400)
            self.assertFailedPreparedResponse(data, response)


@override_settings(ALLOWED_HOSTS=['localhost'])
@freeze_time(datetime(2020, 10, 29, 20, 15, 35))  # when we recorded these requests
class PreparedAcmeNewAccountViewTestCase(AcmePreparedRequestsTestCaseMixin, DjangoCAWithCATestCase):
    """Test creating a new account."""

    expected_status_code = HTTPStatus.CREATED
    view_name = 'AcmeNewAccountView'

    def setUp(self):
        super().setUp()
        self.url = reverse('django_ca:acme-new-account', kwargs={'serial': self.ca_serial})

    def assertFailedPreparedResponse(self, data, response):
        # Test that *no* account was created
        self.assertEqual(AcmeAccount.objects.all().count(), 0)

    def get_nonce(self, ca=None):
        """Get a nonce with an actualy request."""
        if ca is None:
            ca = self.cas['root']

        url = reverse('django_ca:acme-new-nonce', kwargs={'serial': ca.serial})
        response = self.client.head(url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        return response['replay-nonce']

    def assertPreparedResponse(self, data, response, celery_mock):
        account = AcmeAccount.objects.get(thumbprint=data['thumbprint'])
        uri = response.wsgi_request.build_absolute_uri
        kwargs = {'serial': self.ca.serial, 'pk': account.pk}
        self.assertEqual(response['Location'], uri(
            reverse('django_ca:acme-account', kwargs=kwargs)
        ))
        # An example response can be found in RFC 8555, section 7.3
        # https://tools.ietf.org/html/rfc8555#section-7.3
        self.assertEqual(response.json(), {
            'status': 'valid',
            'contact': ['mailto:user@localhost'],
            'orders': uri(reverse('django_ca:acme-account-orders', kwargs=kwargs))
        })


@override_settings(ALLOWED_HOSTS=['localhost'])
@freeze_time(datetime(2020, 10, 29, 20, 15, 35))  # when we recorded these requests
class PreparedAcmeNewOrderViewTestCase(AcmePreparedRequestsTestCaseMixin, DjangoCAWithCATestCase):
    """Test creating a new order."""

    expected_status_code = HTTPStatus.CREATED
    view_name = 'AcmeNewOrderView'

    def setUp(self):
        super().setUp()
        self.url = reverse('django_ca:acme-new-order', kwargs={'serial': self.ca_serial})
        self.done = {}

    def before_prepared_request(self, data):
        # pylint: disable=attribute-defined-outside-init
        self.account = AcmeAccount.objects.create(
            pk=data['account_pk'], contact='user@localhost', ca=self.ca, terms_of_service_agreed=True,
            pem=data['pem'], thumbprint=data['thumbprint'])

    def assertPreparedResponse(self, data, response, celery_mock):
        self.assertEqual(list(AcmeAccount.objects.all()), [self.account])

        order = AcmeOrder.objects.exclude(pk__in=[o.pk for o in self.done.values()]).get(account=self.account)
        self.done[data['nonce']] = order

        self.assertEqual(order.account, self.account)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.expires, timezone.now() + ca_settings.ACME_ORDER_VALIDITY)
        self.assertIsNone(order.not_before)
        self.assertIsNone(order.not_after)
        self.assertEqual(order.acme_finalize_url,
                         f'/django_ca/acme/{self.ca_serial}/order/{order.slug}/finalize/')
        # pylint: disable=no-member
        with self.assertRaises(AcmeOrder.acmecertificate.RelatedObjectDoesNotExist):
            self.assertIsNone(order.acmecertificate)
        # pylint: enable=no-member

        auths = order.authorizations.all()
        self.assertEqual(len(auths), 1)
        auth = auths[0]
        self.assertEqual(auth.status, 'pending')
        self.assertEqual(auth.type, 'dns')
        self.assertEqual(auth.value, 'localhost')
        self.assertEqual(auth.expires, order.expires)
        self.assertFalse(auth.wildcard)

        # Challenges are only created once the selected authorization is retrieved, not when order is created
        self.assertFalse(auth.challenges.exists())


@override_settings(ALLOWED_HOSTS=['localhost'])
@freeze_time(datetime(2020, 10, 29, 20, 15, 35))  # when we recorded these requests
class PreparedAcmeAuthorizationViewTestCase(AcmePreparedRequestsTestCaseMixin, DjangoCAWithCATestCase):
    """Test creating a new order."""

    view_name = 'AcmeAuthorizationView'

    def before_prepared_request(self, data):
        acc = AcmeAccount.objects.get_or_create(thumbprint=data['thumbprint'], defaults={
            'pk': data['account_pk'], 'contact': 'user@localhost', 'ca': self.ca,
            'terms_of_service_agreed': True, 'pem': data['pem'],
        })[0]
        order = AcmeOrder.objects.get_or_create(account=acc, slug=data['order'])[0]
        AcmeAccountAuthorization.objects.get_or_create(order=order, slug=data['auth'], defaults={
            'value': 'localhost'
        })

    def get_url(self, data):
        return reverse('django_ca:acme-authz', kwargs={'serial': self.ca_serial, 'slug': data['auth']})


@override_settings(ALLOWED_HOSTS=['localhost'])
@freeze_time(datetime(2020, 10, 29, 20, 15, 35))  # when we recorded these requests
class PreparedAcmeChallengeViewTestCase(AcmePreparedRequestsTestCaseMixin, DjangoCAWithCATestCase):
    """Test retrieving a challenge."""

    view_name = 'AcmeChallengeView'

    def assertLinkRelations(self, response, ca=None, **kwargs):  # pylint: disable=invalid-name
        if response.status_code < HTTPStatus.BAD_REQUEST:
            kwargs.setdefault('up', response.wsgi_request.build_absolute_uri(self.challenge.acme_url))
        super().assertLinkRelations(response=response, ca=ca, **kwargs)

    def before_prepared_request(self, data):
        acc = AcmeAccount.objects.get_or_create(thumbprint=data['thumbprint'], defaults={
            'pk': data['account_pk'], 'contact': 'user@localhost', 'ca': self.ca,
            'terms_of_service_agreed': True, 'pem': data['pem'],
        })[0]
        order = AcmeOrder.objects.create(account=acc, slug=data['order'])
        auth = AcmeAccountAuthorization.objects.create(order=order, slug=data['auth'], value='localhost')

        self.challenge = AcmeChallenge.objects.create(  # pylint: disable=attribute-defined-outside-init
            slug=data['challenge'], auth=auth, type=AcmeChallenge.TYPE_HTTP_01
        )

    def get_url(self, data):
        return reverse('django_ca:acme-challenge', kwargs={
            'serial': self.ca_serial,
            'slug': data['challenge'],
        })


@override_settings(ALLOWED_HOSTS=['localhost'])
@freeze_time(datetime(2020, 10, 29, 20, 15, 35))  # when we recorded these requests
class PreparedAcmeOrderFinalizeViewTestCase(AcmePreparedRequestsTestCaseMixin, DjangoCAWithCATestCase):
    """Test retrieving a challenge."""

    view_name = 'AcmeOrderFinalizeView'

    def before_prepared_request(self, data):
        acc = AcmeAccount.objects.get_or_create(thumbprint=data['thumbprint'], defaults={
            'pk': data['account_pk'], 'contact': 'user@localhost', 'ca': self.ca,
            'terms_of_service_agreed': True, 'pem': data['pem'],
        })[0]
        AcmeOrder.objects.create(account=acc, slug=data['order'], status=AcmeOrder.STATUS_READY)

    def get_url(self, data):
        return reverse('django_ca:acme-order-finalize', kwargs={
            'serial': self.ca_serial,
            'slug': data['order'],
        })


@override_settings(ALLOWED_HOSTS=['localhost'])
@freeze_time(datetime(2020, 10, 29, 20, 15, 35))  # when we recorded these requests
class PreparedAcmeOrderViewTestCase(AcmePreparedRequestsTestCaseMixin, DjangoCAWithCATestCase):
    """Test retrieving a challenge."""

    view_name = 'AcmeOrderView'

    def before_prepared_request(self, data):
        acc = AcmeAccount.objects.get_or_create(thumbprint=data['thumbprint'], defaults={
            'pk': data['account_pk'], 'contact': 'user@localhost', 'ca': self.ca,
            'terms_of_service_agreed': True, 'pem': data['pem'],
        })[0]
        AcmeOrder.objects.create(account=acc, slug=data['order'], status=AcmeOrder.STATUS_READY)

    def get_url(self, data):
        return reverse('django_ca:acme-order', kwargs={
            'serial': self.ca_serial,
            'slug': data['order'],
        })


@override_settings(ALLOWED_HOSTS=['localhost'])
@freeze_time(datetime(2020, 10, 29, 20, 15, 35))  # when we recorded these requests
class PreparedAcmeCertificateViewTestCase(AcmePreparedRequestsTestCaseMixin, DjangoCAWithCertTestCase):
    """Test retrieving a challenge."""

    view_name = 'AcmeCertificateView'

    def assertAcmeResponse(self, response, ca=None):
        """This view does not return normal ACME responses but a certificate bundle."""
        self.assertLinkRelations(response, ca=ca)
        self.assertEqual(response['Content-Type'], 'application/pem-certificate-chain')

    def before_prepared_request(self, data):
        acc = AcmeAccount.objects.get_or_create(thumbprint=data['thumbprint'], defaults={
            'pk': data['account_pk'], 'contact': 'user@localhost', 'ca': self.ca,
            'terms_of_service_agreed': True, 'pem': data['pem'],
        })[0]
        order = AcmeOrder.objects.create(account=acc, slug=data['order'])
        AcmeCertificate.objects.create(slug=data['cert'], order=order, cert=self.certs['root-cert'],
                                       csr=data['csr'])

    def get_url(self, data):
        return reverse('django_ca:acme-cert', kwargs={
            'serial': self.ca_serial,
            'slug': data['cert'],
        })
