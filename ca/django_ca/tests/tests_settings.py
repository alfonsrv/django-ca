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
# see <http://www.gnu.org/licenses/>

"""Test cases for the ``ca_settings`` module."""

from datetime import timedelta
from unittest import mock

from django.core.exceptions import ImproperlyConfigured

from .. import ca_settings
from ..subject import get_default_subject
from .base import DjangoCATestCase


class SettingsTestCase(DjangoCATestCase):
    """Test some standard settings."""

    def test_none_profiles(self):
        """Test removing a profile by setting it to None."""
        self.assertIn('client', ca_settings.CA_PROFILES)

        with self.settings(CA_PROFILES={'client': None}):
            self.assertNotIn('client', ca_settings.CA_PROFILES)

    def test_ca_profile_update(self):
        """Test adding a profile in settings."""
        desc = 'testdesc'
        with self.settings(CA_PROFILES={'client': {'desc': desc}}):
            self.assertEqual(ca_settings.CA_PROFILES['client']['desc'], desc)

    def test_acme_order_validity(self):
        """Test that ACME_ORDER_VALIDITY can be set to an int."""
        with self.settings(ACME_ORDER_VALIDITY=1):
            self.assertEqual(ca_settings.ACME_ORDER_VALIDITY, timedelta(days=1))

    def test_use_celery(self):
        """Test CA_USE_CELERY setting."""
        with self.settings(CA_USE_CELERY=False):
            self.assertFalse(ca_settings.CA_USE_CELERY)
        with self.settings(CA_USE_CELERY=True):
            self.assertTrue(ca_settings.CA_USE_CELERY)
        with self.settings(CA_USE_CELERY=None):
            self.assertTrue(ca_settings.CA_USE_CELERY)

        # mock a missing Celery installation
        with mock.patch.dict('sys.modules', celery=None), self.settings(CA_USE_CELERY=None):
            self.assertFalse(ca_settings.CA_USE_CELERY)
        with mock.patch.dict('sys.modules', celery=None), self.settings(CA_USE_CELERY=False):
            self.assertFalse(ca_settings.CA_USE_CELERY)


class DefaultCATestCase(DjangoCATestCase):
    """Test the :ref:`CA_DEFAULT_CA <settings-ca-default-ca>` setting."""

    def test_no_setting(self):
        """Test empty setting."""
        with self.settings(CA_DEFAULT_CA=''):
            self.assertEqual(ca_settings.CA_DEFAULT_CA, '')

    def test_unsanitized_setting(self):
        """Test that values are sanitized properly."""
        with self.settings(CA_DEFAULT_CA='0a:bc'):
            self.assertEqual(ca_settings.CA_DEFAULT_CA, 'ABC')

    def test_serial_zero(self):
        """Test that a '0' serial is not stripped."""
        with self.settings(CA_DEFAULT_CA='0'):
            self.assertEqual(ca_settings.CA_DEFAULT_CA, '0')


class ImproperlyConfiguredTestCase(DjangoCATestCase):
    """Test various invalid configurations."""

    def assertImproperlyConfigured(self, msg):  # pylint: disable=invalid-name; unittest standard
        """Minor shortcut to ``assertRaisesRegex``."""
        return self.assertRaisesRegex(ImproperlyConfigured, msg)

    def test_default_ecc_curve(self):
        """Test invalid ``CA_DEFAULT_ECC_CURVE``."""
        with self.assertImproperlyConfigured(r'^Unkown CA_DEFAULT_ECC_CURVE: foo$'):
            with self.settings(CA_DEFAULT_ECC_CURVE='foo'):
                pass

        with self.assertImproperlyConfigured(r'^ECDH: Not an EllipticCurve\.$'):
            with self.settings(CA_DEFAULT_ECC_CURVE='ECDH'):
                pass

        with self.assertImproperlyConfigured('^CA_DEFAULT_KEY_SIZE cannot be lower then 1024$'):
            with self.settings(CA_MIN_KEY_SIZE=1024, CA_DEFAULT_KEY_SIZE=512):
                pass

    def test_digest_algorithm(self):
        """Test invalid ``CA_DIGEST_ALGORITHM``."""
        with self.assertImproperlyConfigured(r'^Unkown CA_DIGEST_ALGORITHM: foo$'):
            with self.settings(CA_DIGEST_ALGORITHM='foo'):
                pass

    def test_default_expires(self):
        """Test invalid ``CA_DEFAULT_EXPIRES``."""
        with self.assertImproperlyConfigured(r'^CA_DEFAULT_EXPIRES: foo: Must be int or timedelta$'):
            with self.settings(CA_DEFAULT_EXPIRES='foo'):
                pass

        with self.assertImproperlyConfigured(
                r'^CA_DEFAULT_EXPIRES: -3 days, 0:00:00: Must have positive value$'):
            with self.settings(CA_DEFAULT_EXPIRES=timedelta(days=-3)):
                pass

    def test_default_subject(self):
        """Test invalid ``CA_DEFAULT_SUBJECT``."""
        with self.assertImproperlyConfigured(r'^CA_DEFAULT_SUBJECT: Invalid subject: True$'):
            with self.settings(CA_DEFAULT_SUBJECT=True):
                get_default_subject()

        with self.assertImproperlyConfigured(r'^CA_DEFAULT_SUBJECT: Invalid OID: XYZ$'):
            with self.settings(CA_DEFAULT_SUBJECT={'XYZ': 'error'}):
                get_default_subject()

    def test_use_celery(self):
        """Test that CA_USE_CELERY=True and a missing Celery installation throws an error."""
        # Setting sys.modules['celery'] (modules cache) to None will cause the next import of that module
        # to trigger an import error:
        #   https://medium.com/python-pandemonium/how-to-test-your-imports-1461c1113be1
        #   https://docs.python.org/3.8/reference/import.html#the-module-cache
        with mock.patch.dict('sys.modules', celery=None):
            msg = r'^CA_USE_CELERY set to True, but Celery is not installed$'

            with self.assertImproperlyConfigured(msg), self.settings(CA_USE_CELERY=True):
                pass

    def test_invalid_setting(self):
        """Test setting an invalid CA."""
        with self.assertImproperlyConfigured(r'^CA_DEFAULT_CA: ABCX: Serial contains invalid characters\.$'):
            with self.settings(CA_DEFAULT_CA='0a:bc:x'):
                pass
