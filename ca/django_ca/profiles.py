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

"""Module for handling certificate profiles."""

import typing
from datetime import datetime, timedelta
from threading import local
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union

from cryptography import x509
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID, NameOID

from django.urls import reverse

from django_ca import ca_settings, constants, typehints
from django_ca.constants import EXTENSION_DEFAULT_CRITICAL, EXTENSION_KEY_OIDS, EXTENSION_KEYS
from django_ca.extensions import parse_extension, serialize_extension
from django_ca.extensions.utils import format_extensions, get_formatting_context
from django_ca.signals import pre_sign_cert
from django_ca.typehints import (
    AllowedHashTypes,
    Expires,
    ExtensionMapping,
    ParsableExtension,
    SerializedExtension,
    SerializedProfile,
)
from django_ca.utils import (
    get_cert_builder,
    merge_x509_names,
    parse_expires,
    parse_general_name,
    serialize_name,
    sort_name,
    x509_name,
)

if typing.TYPE_CHECKING:
    from django_ca.models import CertificateAuthority


class Profile:
    """A certificate profile defining properties and extensions of a certificate.

    Instances of this class usually represent profiles defined in :ref:`CA_PROFILES <settings-ca-profiles>`,
    but you can also create your own profile to create a different type of certificate. An instance of this
    class can be used to create a signed certificate based on the given CA::

        >>> Profile('example', subject='/C=AT', extensions={'ocsp_no_check': {}})
        <Profile: example>
    """

    algorithm: Optional[AllowedHashTypes] = None
    extensions: Dict[x509.ObjectIdentifier, Optional[x509.Extension[x509.ExtensionType]]]

    def __init__(
        self,
        name: str,
        subject: Optional[Union[typing.Literal[False], x509.Name, Iterable[Tuple[str, str]]]] = None,
        algorithm: Optional[str] = None,
        extensions: Optional[
            Dict[str, Optional[Union[ParsableExtension, x509.Extension[x509.ExtensionType]]]]
        ] = None,
        cn_in_san: bool = True,
        expires: Optional[Union[int, timedelta]] = None,
        description: str = "",
        autogenerated: bool = False,
        add_crl_url: bool = True,
        add_ocsp_url: bool = True,
        add_issuer_url: bool = True,
        add_issuer_alternative_name: bool = True,
    ) -> None:
        # pylint: disable=too-many-arguments
        self.name = name

        if isinstance(expires, int):
            expires = timedelta(days=expires)
        if extensions is None:
            extensions = {}
        if subject is None:
            self.subject: Optional[Union[typing.Literal[False], x509.Name]] = ca_settings.CA_DEFAULT_SUBJECT
        elif subject is False:
            self.subject = False
        elif isinstance(subject, x509.Name):
            self.subject = subject
        else:
            self.subject = x509_name(subject)

        if algorithm is not None:
            try:
                self.algorithm = constants.HASH_ALGORITHM_TYPES[algorithm]()
            except KeyError as ex:
                raise ValueError(f"{algorithm}: Unknown hash algorithm.") from ex

        self.cn_in_san = cn_in_san
        self.expires = expires or ca_settings.CA_DEFAULT_EXPIRES
        self.add_crl_url = add_crl_url
        self.add_issuer_url = add_issuer_url
        self.add_ocsp_url = add_ocsp_url
        self.add_issuer_alternative_name = add_issuer_alternative_name
        self.description = description
        self.autogenerated = autogenerated

        # Instantiating mutable dict here and not as class attribute to improve isolation
        self.extensions: Dict[str, Optional[x509.Extension[x509.ExtensionType]]] = {}

        # cast extensions to their respective classes
        for key, extension in extensions.items():
            if isinstance(extension, x509.Extension):
                self.extensions[extension.oid] = extension
            elif extension is None:
                # None value explicitly deactivates/unsets an extension in the admin interface
                self.extensions[EXTENSION_KEY_OIDS[key]] = None
            else:
                parsed_extension = parse_extension(key, extension)
                self.extensions[parsed_extension.oid] = parsed_extension

        # set some sane extension defaults
        self.extensions.setdefault(
            ExtensionOID.BASIC_CONSTRAINTS,
            x509.Extension(
                oid=ExtensionOID.BASIC_CONSTRAINTS,
                critical=EXTENSION_DEFAULT_CRITICAL[ExtensionOID.BASIC_CONSTRAINTS],
                value=x509.BasicConstraints(ca=False, path_length=None),
            ),
        )

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, (Profile, DefaultProfileProxy)):
            return False
        algo = isinstance(value.algorithm, type(self.algorithm))

        return (
            self.name == value.name
            and self.subject == value.subject
            and algo
            and self.extensions == value.extensions
            and self.cn_in_san == value.cn_in_san
            and self.expires == value.expires
            and self.add_crl_url == value.add_crl_url
            and self.add_issuer_url == value.add_issuer_url
            and self.add_ocsp_url == value.add_ocsp_url
            and self.add_issuer_alternative_name == value.add_issuer_alternative_name
            and self.description == value.description
        )

    def __repr__(self) -> str:
        return f"<Profile: {self.name}>"

    def __str__(self) -> str:
        return repr(self)

    def _get_extensions(self, extensions: typehints.ExtensionDict) -> None:
        for oid, ext in self.extensions.items():
            if ext is None:
                extensions.pop(oid, None)
            else:
                extensions.setdefault(oid, ext)

    def create_cert(
        self,
        ca: "CertificateAuthority",
        csr: x509.CertificateSigningRequest,
        *,
        subject: Optional[x509.Name] = None,
        expires: Expires = None,
        algorithm: Optional[AllowedHashTypes] = None,
        extensions: Optional[Iterable[x509.Extension[x509.ExtensionType]]] = None,
        cn_in_san: Optional[bool] = None,
        add_crl_url: Optional[bool] = None,
        add_ocsp_url: Optional[bool] = None,
        add_issuer_url: Optional[bool] = None,
        add_issuer_alternative_name: Optional[bool] = None,
        password: Optional[Union[str, bytes]] = None,
    ) -> x509.Certificate:
        """Create a x509 certificate based on this profile, the passed CA and input parameters.

        This function is the core function used to create x509 certificates. In its simplest form, you only
        need to pass a ca, a CSR and a subject to get a valid certificate::

            >>> profile = get_profile('webserver')
            >>> profile.create_cert(ca, csr, subject=x509_name('/CN=example.com'))  # doctest: +ELLIPSIS
            <Certificate(subject=<Name(...,CN=example.com)>, ...)>

        .. versionchanged:: 1.26.0

           All optional arguments have to be passed as keyword arguments.

        The function will add CRL, OCSP, Issuer and IssuerAlternativeName URLs based on the CA if the profile
        has the *add_crl_url*, *add_ocsp_url* and *add_issuer_url* and *add_issuer_alternative_name* values
        set. Parameters to this function with the same name allow you override this behavior.

        The function allows you to override profile values using the *expires* and *algorithm* values. You can
        pass additional *extensions* as a list, which will override any extensions from the profile, but the
        CA passed will append to these extensions unless the *add_...* values are ``False``.

        Parameters
        ----------

        ca : :py:class:`~django_ca.models.CertificateAuthority`
            The CA to sign the certificate with.
        csr : :py:class:`~cg:cryptography.x509.CertificateSigningRequest`
            The CSR for the certificate.
        subject : :py:class:`~cg:cryptography.x509.Name`, optional
            Subject for the certificate. The value will be merged with the subject of the profile. If not
            given, the certificate's subject will be identical to the subject from the profile.
        expires : int or datetime or timedelta, optional
            Override when this certificate will expire.
        algorithm : :py:class:`~cg:cryptography.hazmat.primitives.hashes.HashAlgorithm`, optional
            Override the hash algorithm used when signing the certificate.
        extensions : list or of :py:class:`~cg:cryptography.x509.Extension`
            List of additional extensions to set for the certificate. Note that values from the CA might
            update the passed extensions: For example, if you pass an
            :py:class:`~cg:cryptography.x509.IssuerAlternativeName` extension, *add_issuer_alternative_name*
            is ``True`` and the passed CA has an IssuerAlternativeName set, that value will be appended to the
            extension you pass here.
        cn_in_san : bool, optional
            Override if the commonName should be added as an SubjectAlternativeName. If not passed, the value
            set in the profile is used.
        add_crl_url : bool, optional
            Override if any CRL URLs from the CA should be added to the CA. If not passed, the value set in
            the profile is used.
        add_ocsp_url : bool, optional
            Override if any OCSP URLs from the CA should be added to the CA. If not passed, the value set in
            the profile is used.
        add_issuer_url : bool, optional
            Override if any Issuer URLs from the CA should be added to the CA. If not passed, the value set in
            the profile is used.
        add_issuer_alternative_name : bool, optional
            Override if any IssuerAlternativeNames from the CA should be added to the CA. If not passed, the
            value set in the profile is used.
        password: bytes or str, optional
            The password to the private key of the CA.

        Returns
        -------

        cryptography.x509.Certificate
            The signed certificate.
        """

        # Get overrides values from profile if not passed as parameter
        if cn_in_san is None:
            cn_in_san = self.cn_in_san
        if add_crl_url is None:
            add_crl_url = self.add_crl_url
        if add_ocsp_url is None:
            add_ocsp_url = self.add_ocsp_url
        if add_issuer_url is None:
            add_issuer_url = self.add_issuer_url
        if add_issuer_alternative_name is None:
            add_issuer_alternative_name = self.add_issuer_alternative_name

        if extensions is None:
            cert_extensions: typehints.ExtensionDict = {}
        else:
            cert_extensions = {ext.oid: ext for ext in extensions}

        # Get extensions from profile
        self._get_extensions(cert_extensions)

        self._update_from_ca(
            ca,
            cert_extensions,
            add_crl_url=add_crl_url,
            add_ocsp_url=add_ocsp_url,
            add_issuer_url=add_issuer_url,
            add_issuer_alternative_name=add_issuer_alternative_name,
        )

        if self.subject is not False and self.subject is not None:
            if subject is not None:
                subject = merge_x509_names(self.subject, subject)
            else:
                subject = self.subject

        # Add first DNSName/IPAddress from subjectAlternativeName as commonName if not present in the subject
        subject = self._update_cn_from_san(subject, cert_extensions)

        if subject is None:
            raise ValueError("Cannot determine subject for certificate.")
        subject = sort_name(subject)

        if algorithm is None and ca.algorithm:
            if self.algorithm is not None:
                algorithm = self.algorithm
            else:
                algorithm = ca.algorithm

        # Make sure that expires is a fixed timestamp
        expires = self.get_expires(expires)

        # Finally, add the commonName as a subjectAlternativeName if not already present.
        self._update_san_from_cn(cn_in_san, subject=subject, extensions=cert_extensions)

        if not subject.get_attributes_for_oid(NameOID.COMMON_NAME) and not cert_extensions.get(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        ):
            raise ValueError("Must name at least a CN or a subjectAlternativeName.")

        serial = x509.random_serial_number()
        signer_serial = ca.pub.loaded.serial_number
        context = self._get_formatting_context(serial, signer_serial)
        format_extensions(cert_extensions, context)

        extensions = list(cert_extensions.values())

        pre_sign_cert.send(
            sender=self.__class__,
            ca=ca,
            csr=csr,
            expires=expires,
            algorithm=algorithm,
            subject=subject,
            extensions=extensions,
            password=password,
        )

        public_key = csr.public_key()
        builder = get_cert_builder(expires, serial=serial)
        builder = builder.public_key(public_key)
        builder = builder.issuer_name(ca.subject)
        builder = builder.subject_name(subject)

        for extension in extensions:
            builder = builder.add_extension(extension.value, critical=extension.critical)

        # Add the SubjectKeyIdentifier
        if ExtensionOID.SUBJECT_KEY_IDENTIFIER not in cert_extensions:
            builder = builder.add_extension(
                x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False
            )

        return builder.sign(private_key=ca.key(password), algorithm=algorithm)

    def _get_formatting_context(self, serial: int, signer_serial: int) -> Dict[str, Union[str, int]]:
        context = get_formatting_context(serial, signer_serial)
        kwargs = {"serial": context["SIGNER_SERIAL_HEX"]}
        context["OCSP_PATH"] = reverse("django_ca:ocsp-cert-post", kwargs=kwargs).lstrip("/")
        context["CRL_PATH"] = reverse("django_ca:crl", kwargs=kwargs).lstrip("/")
        return context

    def get_expires(self, expires: Expires) -> datetime:
        """Get expiry for the given expiry timestamp."""
        if expires is None:
            expires = self.expires
        return parse_expires(expires)

    def serialize(self) -> SerializedProfile:
        """Function to serialize a profile.

        This is function is called by the admin interface to retrieve profile information to the browser, so
        the value returned by this function should always be JSON serializable.
        """
        extensions: Dict[str, Optional[SerializedExtension]] = {}

        for key, extension in self.extensions.items():
            if extension is None:
                # None value explicitly deactivates/unsets an extension in the admin interface
                extensions[EXTENSION_KEYS[key]] = None
            else:
                extensions[EXTENSION_KEYS[key]] = serialize_extension(extension)

        serialized_name = None
        if self.subject is not None and self.subject is not False:
            serialized_name = serialize_name(self.subject)

        data: SerializedProfile = {
            "cn_in_san": self.cn_in_san,
            "description": self.description,
            "subject": serialized_name,
            "extensions": extensions,
        }

        return data

    def _update_authority_information_access(
        self,
        extensions: ExtensionMapping,
        ca_extensions: ExtensionMapping,
        add_issuer_url: bool,
        add_ocsp_url: bool,
    ) -> None:
        oid = ExtensionOID.AUTHORITY_INFORMATION_ACCESS

        # If there is no extension from the CA there is nothing to merge.
        if oid not in ca_extensions:
            return
        ca_aia_ext = typing.cast(x509.Extension[x509.AuthorityInformationAccess], ca_extensions[oid])
        critical = ca_aia_ext.critical

        has_issuer = has_ocsp = False
        access_descriptions: List[x509.AccessDescription] = []

        if oid in extensions:
            cert_aia_ext = typing.cast(x509.Extension[x509.AuthorityInformationAccess], extensions[oid])
            access_descriptions = list(cert_aia_ext.value)
            has_ocsp = any(
                ad.access_method == AuthorityInformationAccessOID.OCSP for ad in access_descriptions
            )
            has_issuer = any(
                ad.access_method == AuthorityInformationAccessOID.CA_ISSUERS for ad in access_descriptions
            )
            critical = cert_aia_ext.critical

        if add_issuer_url is True and has_issuer is False:
            access_descriptions += [
                ad
                for ad in ca_aia_ext.value
                if ad not in access_descriptions
                and ad.access_method == AuthorityInformationAccessOID.CA_ISSUERS
            ]
        if add_ocsp_url is True and has_ocsp is False:
            access_descriptions += [
                ad
                for ad in ca_aia_ext.value
                if ad not in access_descriptions and ad.access_method == AuthorityInformationAccessOID.OCSP
            ]

        # Finally sort by OID so that we have more predictable behavior
        access_descriptions = sorted(access_descriptions, key=lambda ad: ad.access_method.dotted_string)

        if access_descriptions:
            extensions[oid] = x509.Extension(
                oid=oid,
                critical=critical,
                value=x509.AuthorityInformationAccess(access_descriptions),
            )

    def _add_crl_distribution_points(
        self, extensions: ExtensionMapping, ca_extensions: ExtensionMapping
    ) -> None:
        """Add the CRLDistribution Points extension with the endpoint from the Certificate Authority."""
        if ExtensionOID.CRL_DISTRIBUTION_POINTS not in ca_extensions:
            return
        if ExtensionOID.CRL_DISTRIBUTION_POINTS in extensions:
            return
        extensions[ExtensionOID.CRL_DISTRIBUTION_POINTS] = ca_extensions[ExtensionOID.CRL_DISTRIBUTION_POINTS]

    def _update_issuer_alternative_name(
        self, extensions: ExtensionMapping, ca_extensions: ExtensionMapping
    ) -> None:
        oid = ExtensionOID.ISSUER_ALTERNATIVE_NAME
        if oid in ca_extensions and oid not in extensions:
            extensions[oid] = ca_extensions[oid]

    def _update_from_ca(
        self,
        ca: "CertificateAuthority",
        extensions: ExtensionMapping,
        add_crl_url: bool,
        add_ocsp_url: bool,
        add_issuer_url: bool,
        add_issuer_alternative_name: bool,
    ) -> None:
        """Update data from the given CA.

        * Sets the AuthorityKeyIdentifier extension
        * Sets the OCSP url if add_ocsp_url is True
        * Sets a CRL URL if add_crl_url is True
        * Adds an IssuerAlternativeName if add_issuer_alternative_name is True

        """

        ca_extensions = ca.extensions_for_certificate

        # client can set its own AuthorityKeyIdentifier extension (currently used for the alt-extensions
        # certificate when creating fixtures).
        extensions.setdefault(
            ExtensionOID.AUTHORITY_KEY_IDENTIFIER, ca.get_authority_key_identifier_extension()
        )

        if add_crl_url is True:
            self._add_crl_distribution_points(extensions, ca_extensions)

        self._update_authority_information_access(
            extensions, ca_extensions, add_issuer_url=add_issuer_url, add_ocsp_url=add_ocsp_url
        )

        if add_issuer_alternative_name is not False:
            self._update_issuer_alternative_name(extensions, ca_extensions)

    def _update_cn_from_san(
        self, subject: Optional[x509.Name], extensions: ExtensionMapping
    ) -> Optional[x509.Name]:
        # If we already have a common name, return the subject unchanged
        if subject is not None and subject.get_attributes_for_oid(NameOID.COMMON_NAME):
            return subject

        if ExtensionOID.SUBJECT_ALTERNATIVE_NAME in extensions:
            san_ext = typing.cast(
                x509.Extension[x509.SubjectAlternativeName],
                extensions[ExtensionOID.SUBJECT_ALTERNATIVE_NAME],
            )
            cn_types = (x509.DNSName, x509.IPAddress)
            common_name = next(
                (str(val.value) for val in san_ext.value if isinstance(val, cn_types)),
                None,
            )

            if common_name is not None:
                common_name_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])

                if subject is None:
                    return common_name_name
                return merge_x509_names(subject, common_name_name)

        return subject

    def _update_san_from_cn(self, cn_in_san: bool, subject: x509.Name, extensions: ExtensionMapping) -> None:
        if cn_in_san is False:
            return

        if not (common_name_attributes := subject.get_attributes_for_oid(NameOID.COMMON_NAME)):
            return

        common_name_value = typing.cast(str, common_name_attributes[0].value)
        try:
            common_name = parse_general_name(common_name_value)
        except ValueError as ex:
            raise ValueError(
                f"{common_name_value}: Could not parse CommonName as subjectAlternativeName."
            ) from ex

        if ExtensionOID.SUBJECT_ALTERNATIVE_NAME in extensions:
            san_ext = typing.cast(
                x509.Extension[x509.SubjectAlternativeName],
                extensions[ExtensionOID.SUBJECT_ALTERNATIVE_NAME],
            )

            if common_name not in san_ext.value:
                extensions[ExtensionOID.SUBJECT_ALTERNATIVE_NAME] = x509.Extension(
                    oid=ExtensionOID.SUBJECT_ALTERNATIVE_NAME,
                    critical=san_ext.critical,
                    value=x509.SubjectAlternativeName(list(san_ext.value) + [common_name]),
                )
        else:
            extensions[ExtensionOID.SUBJECT_ALTERNATIVE_NAME] = x509.Extension(
                oid=ExtensionOID.SUBJECT_ALTERNATIVE_NAME,
                critical=False,
                value=x509.SubjectAlternativeName([common_name]),
            )


def get_profile(name: Optional[str] = None) -> Profile:
    """Get profile by the given name.

    Raises ``KeyError`` if the profile is not defined.

    Parameters
    ----------

    name : str, optional
        The name of the profile. If ``None``, the profile configured by
        :ref:`CA_DEFAULT_PROFILE <settings-ca-default-profile>` is used.
    """
    if name is None:
        name = ca_settings.CA_DEFAULT_PROFILE
    return Profile(name, **ca_settings.CA_PROFILES[name])


class Profiles:
    """A profile handler similar to Django's CacheHandler."""

    def __init__(self) -> None:
        self._profiles = local()

    def __getitem__(self, name: Optional[str]) -> Profile:
        if name is None:
            name = ca_settings.CA_DEFAULT_PROFILE

        try:
            return typing.cast(Profile, self._profiles.profiles[name])
        except AttributeError:
            self._profiles.profiles = {}
        except KeyError:
            pass

        self._profiles.profiles[name] = get_profile(name)
        return typing.cast(Profile, self._profiles.profiles[name])

    def __iter__(self) -> Iterator[Profile]:
        for name in ca_settings.CA_PROFILES:
            yield self[name]

    def _reset(self) -> None:
        self._profiles = local()


profiles = Profiles()


class DefaultProfileProxy:
    """Default profile proxy, similar to Django's DefaultCacheProxy.

    .. NOTE:: We don't implement setattr/delattr, because Profiles are supposed to be read-only anyway.
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(profiles[ca_settings.CA_DEFAULT_PROFILE], name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (DefaultProfileProxy, Profile)):
            return False
        return profiles[ca_settings.CA_DEFAULT_PROFILE] == other

    def __repr__(self) -> str:
        return f"<DefaultProfile: {self.name}>"

    def __str__(self) -> str:
        return repr(self)


profile = DefaultProfileProxy()
