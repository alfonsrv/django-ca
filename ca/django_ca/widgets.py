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

"""Form widgets for django-ca admin interface."""

from django.forms import widgets
from django.utils.translation import gettext as _

from . import ca_settings


class LabeledCheckboxInput(widgets.CheckboxInput):
    """CheckboxInput widget that adds a label and wraps everything in a <span />.

    This is necessary because widgets in MultiValueFields don't render with a label."""

    template_name = 'django_ca/forms/widgets/labeledcheckboxinput.html'

    def __init__(self, label, *args, **kwargs):
        self.label = label
        super().__init__(*args, **kwargs)

    def get_context(self, *args, **kwargs):
        ctx = super().get_context(*args, **kwargs)
        ctx['widget']['label'] = self.label
        return ctx

    class Media:
        css = {
            'all': ('django_ca/admin/css/labeledcheckboxinput.css', ),
        }


class LabeledTextInput(widgets.TextInput):
    """CheckboxInput widget that adds a label and wraps everything in a <span />.

    This is necessary because widgets in MultiValueFields don't render with a label."""

    template_name = 'django_ca/forms/widgets/labeledtextinput.html'

    def __init__(self, label, *args, **kwargs):
        self.label = label
        super().__init__(*args, **kwargs)

    def get_context(self, *args, **kwargs):
        ctx = super().get_context(*args, **kwargs)
        ctx['widget']['label'] = self.label
        ctx['widget']['cssid'] = self.label.lower().replace(' ', '-')
        return ctx

    class Media:
        css = {
            'all': ('django_ca/admin/css/labeledtextinput.css', ),
        }


class SubjectTextInput(LabeledTextInput):
    """Widget used in :py:class:`~django_ca.widgets.SubjectWidget`."""

    template_name = 'django_ca/forms/widgets/subjecttextinput.html'


class ProfileWidget(widgets.Select):
    """Widget for profile selection."""

    template_name = 'django_ca/forms/widgets/profile.html'

    def get_context(self, *args, **kwargs):
        ctx = super().get_context(*args, **kwargs)
        ctx['desc'] = ca_settings.CA_PROFILES[ca_settings.CA_DEFAULT_PROFILE].get(
            'description', ca_settings.CA_PROFILES[ca_settings.CA_DEFAULT_PROFILE].get('desc', ''))
        return ctx

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'django_ca/admin/js/profilewidget.js',
        )


class CustomMultiWidget(widgets.MultiWidget):  # pylint: disable=abstract-method; decompress() in subclasses
    """Wraps the multi widget into a <p> element (base class for other widgets)."""

    template_name = 'django_ca/forms/widgets/custommultiwidget.html'


class SubjectWidget(CustomMultiWidget):
    """Widget for a :py:class:`~django_ca.subject.Subject`."""

    def __init__(self, attrs=None):
        _widgets = (
            SubjectTextInput(label=_('Country'), attrs={'placeholder': '2 character country code'}),
            SubjectTextInput(label=_('State')),
            SubjectTextInput(label=_('Location')),
            SubjectTextInput(label=_('Organization')),
            SubjectTextInput(label=_('Organizational Unit')),
            SubjectTextInput(label=_('CommonName'), attrs={'required': True}),
            SubjectTextInput(label=_('E-Mail')),
        )
        super().__init__(_widgets, attrs)

    def decompress(self, value):
        if value is None:  # pragma: no cover
            return ('', '', '', '', '', '')

        # Multiple OUs are not supported in webinterface
        org_unit = value.get('OU', '')
        if isinstance(org_unit, list) and org_unit:
            org_unit = org_unit[0]

        # Used e.g. for initial form data (e.g. resigning a cert)
        return [
            value.get('C', ''),
            value.get('ST', ''),
            value.get('L', ''),
            value.get('O', ''),
            org_unit,
            value.get('CN', ''),
            value.get('emailAddress', ''),
        ]


class SubjectAltNameWidget(CustomMultiWidget):
    """Widget for a Subject Alternative Name extension."""

    def __init__(self, attrs=None):
        _widgets = (
            widgets.TextInput(),
            LabeledCheckboxInput(label="Include CommonName")
        )
        super().__init__(_widgets, attrs)

    def decompress(self, value):  # pragma: no cover
        if value:
            return value
        return ('', True)


class MultiValueExtensionWidget(CustomMultiWidget):
    """A widget for multiple-choice extensions (e.g. :py:class:`~django_ca.extensions.KeyUsage`."""

    def __init__(self, choices, attrs=None):
        _widgets = (
            widgets.SelectMultiple(choices=choices, attrs=attrs),
            LabeledCheckboxInput(label=_('critical')),
        )
        super().__init__(_widgets, attrs)

    def decompress(self, value):
        if value:
            return value.serialize_value(), value.critical
        return ([], False)
