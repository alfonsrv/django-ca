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

"""Various type aliases used throught different models."""

# pylint: disable=unsubscriptable-object; https://github.com/PyCQA/pylint/issues/3882

import sys
from typing import TYPE_CHECKING
from typing import Dict
from typing import Iterable
from typing import List
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import TypeVar
from typing import Union

from cryptography import x509
from cryptography.x509.certificate_transparency import SignedCertificateTimestamp

# pylint: disable=useless-import-alias; or mypy won't consider imports as "re-exported"
if sys.version_info >= (3, 8):  # pragma: only py>=3.8
    from typing import SupportsIndex as SupportsIndex
    from typing import TypedDict as TypedDict
else:  # pragma: only py<3.8
    # pylint: disable=import-error; typing_extensions is not present in newer environments
    from typing_extensions import SupportsIndex as SupportsIndex  # NOQA: F401
    from typing_extensions import TypedDict as TypedDict

    # pylint: enable=import-error
# pylint: enable=useless-import-alias

# GeneralNameList
ParsableRelativeDistinguishedName = Union[str, Iterable[Tuple[str, str]]]
ParsableGeneralName = Union[x509.GeneralName, str]
ParsableGeneralNameList = Iterable[ParsableGeneralName]

SerializedDistributionPoint = TypedDict(
    "SerializedDistributionPoint",
    {
        "full_name": List[str],
        "relative_name": str,
        "crl_issuer": List[str],
        "reasons": List[str],
    },
    total=False,
)
SerializedDistributionPoints = TypedDict(
    "SerializedDistributionPoints",
    {
        "critical": bool,
        "value": List[SerializedDistributionPoint],
    }
)
SerializedNoticeReference = Dict[str, Union[str, List[int]]]
SerializedPolicyQualifier = Union[str, Dict[str, Union[str, SerializedNoticeReference]]]
SerializedPolicyQualifiers = Optional[List[SerializedPolicyQualifier]]

# Looser variants of the above for incoming arguments
LooseNoticeReference = Mapping[str, Union[str, Iterable[int]]]  # List->Iterable/Dict->Mapping
LoosePolicyQualifier = Union[str, Mapping[str, Union[str, LooseNoticeReference]]]  # Dict->Mapping

# Parsable arguments
ParsableDistributionPoint = TypedDict(
    "ParsableDistributionPoint",
    {
        "full_name": ParsableGeneralNameList,
        "relative_name": ParsableRelativeDistinguishedName,
        "crl_issuer": ParsableGeneralNameList,
        "reasons": Iterable[Union[str, x509.ReasonFlags]],
    },
    total=False,
)
ParsablePolicyQualifier = Union[str, x509.UserNotice, LoosePolicyQualifier]
ParsablePolicyIdentifier = Union[str, x509.ObjectIdentifier]
ParsablePolicyInformation = Dict[str, Union[ParsablePolicyQualifier, ParsablePolicyQualifier]]
PolicyQualifier = Union[str, x509.UserNotice]
SerializedPolicyInformation = Dict[str, Union[str, SerializedPolicyQualifiers]]

ExtensionTypeTypeVar = TypeVar("ExtensionTypeTypeVar", bound=x509.ExtensionType)
"""A type variable for a :py:class:`~cg:cryptography.x509.ExtensionType` instance."""

ParsableItem = TypeVar("ParsableItem")
ParsableValue = TypeVar("ParsableValue")

SerializedItem = TypeVar("SerializedItem")
"""TypeVar representing a serialized item for an iterable extension."""

SerializedValue = TypeVar("SerializedValue")
"""TypeVar representing a serialized value for an extension."""

ParsableSubjectKeyIdentifier = Union[str, bytes]

if TYPE_CHECKING:
    ExtensionTypeVar = x509.Extension[ExtensionTypeTypeVar]
    ExtensionType = x509.Extension[x509.ExtensionType]
    SubjectKeyIdentifierType = x509.Extension[x509.SubjectKeyIdentifier]
    UnrecognizedExtensionType = x509.Extension[x509.UnrecognizedExtension]
    TLSFeatureExtensionType = x509.Extension[x509.TLSFeature]
    PrecertificateSignedCertificateTimestampsType = x509.Extension[
        x509.PrecertificateSignedCertificateTimestamps
    ]
else:
    ExtensionType = ExtensionTypeVar = x509.Extension
    SubjectKeyIdentifierType = (
        TLSFeatureExtensionType
    ) = UnrecognizedExtensionType = PrecertificateSignedCertificateTimestampsType = x509.ExtensionType


BasicConstraintsBase = TypedDict("BasicConstraintsBase", {"ca": bool})
ParsableAuthorityInformationAccess = TypedDict(
    "ParsableAuthorityInformationAccess",
    {
        "ocsp": Optional[ParsableGeneralNameList],
        "issuers": Optional[ParsableGeneralNameList],
    },
)
ParsableAuthorityKeyIdentifierDict = TypedDict(
    "ParsableAuthorityKeyIdentifierDict",
    {
        "key_identifier": Optional[bytes],
        "authority_cert_issuer": Iterable[str],
        "authority_cert_serial_number": Optional[int],
    },
    total=False,
)
ParsableAuthorityKeyIdentifier = Union[str, bytes, ParsableAuthorityKeyIdentifierDict]


class ParsableBasicConstraints(BasicConstraintsBase, total=False):
    """Serialized representation of a BasicConstraints extension.

    A value of this type is a dictionary with a ``"ca"`` key with a boolean value. If ``True``, it also
    has a ``"pathlen"`` value that is either ``None`` or an int.
    """

    # pylint: disable=too-few-public-methods; just a TypedDict
    pathlen: Union[int, str]


ParsableNameConstraints = TypedDict(
    "ParsableNameConstraints",
    {
        "permitted": ParsableGeneralNameList,
        "excluded": ParsableGeneralNameList,
    },
    total=False,
)
ParsableNullExtension = TypedDict(
    "ParsableNullExtension",
    {
        "critical": bool,
    },
    total=False,
)
ParsablePolicyConstraints = TypedDict(
    "ParsablePolicyConstraints",
    {
        "require_explicit_policy": int,
        "inhibit_policy_mapping": int,
    },
    total=False,
)


class SerializedBasicConstraints(BasicConstraintsBase, total=False):
    """Serialized representation of a BasicConstraints extension.

    A value of this type is a dictionary with a ``"ca"`` key with a boolean value. If ``True``, it also
    has a ``"pathlen"`` value that is either ``None`` or an int.
    """

    # pylint: disable=too-few-public-methods; just a TypedDict
    pathlen: Optional[int]


SerializedAuthorityInformationAccess = TypedDict(
    "SerializedAuthorityInformationAccess",
    {
        "issuers": List[str],
        "ocsp": List[str],
    },
    total=False,
)
SerializedAuthorityKeyIdentifier = TypedDict(
    "SerializedAuthorityKeyIdentifier",
    {
        "key_identifier": str,
        "authority_cert_issuer": List[str],
        "authority_cert_serial_number": int,
    },
    total=False,
)
SerializedNameConstraints = TypedDict(
    "SerializedNameConstraints",
    {
        "permitted": List[str],
        "excluded": List[str],
    },
)
SerializedPolicyConstraints = TypedDict(
    "SerializedPolicyConstraints",
    {
        "inhibit_policy_mapping": int,
        "require_explicit_policy": int,
    },
    total=False,
)
SerializedSignedCertificateTimestamp = TypedDict(
    "SerializedSignedCertificateTimestamp",
    {
        "log_id": str,
        "timestamp": str,
        "type": str,
        "version": str,
    },
)
"""A dictionary with four keys: log_id, timestamp, type, version, values are all str."""

ParsableSignedCertificateTimestamp = Union[SerializedSignedCertificateTimestamp, SignedCertificateTimestamp]
