# -*- coding: utf-8 -*-
#
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

import importlib

from django import forms

from . import ca_settings
from .subject import Subject
from .utils import GENERAL_NAME_CHOICES
from .utils import SUBJECT_FIELDS
from .widgets import GeneralNameWidget
from .widgets import MultiValueExtensionWidget
from .widgets import SubjectAltNameWidget
from .widgets import SubjectWidget
from .widgets import ListWidget


class SubjectField(forms.MultiValueField):
    def __init__(self, *args, **kwargs):
        fields = (
            forms.CharField(required=False),  # C
            forms.CharField(required=False),  # ST
            forms.CharField(required=False),  # L
            forms.CharField(required=False),  # O
            forms.CharField(required=False),  # OU
            forms.CharField(),  # CN
            forms.CharField(required=False),  # E
        )

        # NOTE: do not pass initial here as this is done on webserver invocation
        #       This screws up tests.
        kwargs.setdefault('widget', SubjectWidget)
        super(SubjectField, self).__init__(fields=fields, require_all_fields=False,
                                           *args, **kwargs)

    def compress(self, values):
        # list comprehension is to filter empty fields
        return Subject([(k, v) for k, v in zip(SUBJECT_FIELDS, values) if v])


class SubjectAltNameField(forms.MultiValueField):
    def __init__(self, *args, **kwargs):
        fields = (
            forms.CharField(required=False),
            forms.BooleanField(required=False),
        )
        kwargs.setdefault('widget', SubjectAltNameWidget)
        initial = ca_settings.CA_PROFILES[ca_settings.CA_DEFAULT_PROFILE].get('cn_in_san', True)
        kwargs.setdefault('initial', ['', initial])
        super(SubjectAltNameField, self).__init__(
            fields=fields, require_all_fields=False, *args, **kwargs)

    def compress(self, values):
        return values


class MultiValueExtensionField(forms.MultiValueField):
    def __init__(self, extension, *args, **kwargs):
        self.extension = extension

        label = kwargs['label']
        initial = ca_settings.CA_PROFILES[ca_settings.CA_DEFAULT_PROFILE].get(label, {})
        kwargs.setdefault('initial', [
            initial.get('value', []),
            initial.get('critical', False),
        ])

        fields = (
            forms.MultipleChoiceField(required=False, choices=extension.CHOICES),
            forms.BooleanField(required=False),
        )

        widget = MultiValueExtensionWidget(choices=extension.CHOICES)
        super(MultiValueExtensionField, self).__init__(
            fields=fields, require_all_fields=False, widget=widget,
            *args, **kwargs)

    def compress(self, values):
        return self.extension({
            'critical': values[1],
            'value': values[0],
        })


class GeneralNameField(forms.MultiValueField):
    def __init__(self, **kwargs):
        fields = (
            forms.ChoiceField(choices=GENERAL_NAME_CHOICES),
            forms.CharField(),
        )
        widget = GeneralNameWidget(choices=GENERAL_NAME_CHOICES)
        super(GeneralNameField, self).__init__(fields=fields, widget=widget, **kwargs)

    def compress(self, values):
        if values:
            mod, name = values[0].rsplit('.', 1)
            mod = importlib.import_module(mod)
            cls = getattr(mod, name)
            return cls(values[1])
        return ('cryptography.x509.general_name.UniformResourceIdentifier', '')


class ListField(forms.Field):
    widget = ListWidget

    def __init__(self, field, widget=None, **kwargs):
        self.field = field

        # instantiate a widget
        widget = widget or self.widget
        if isinstance(widget, type):
            widget = widget(field.widget)

        kwargs['widget'] = widget

        super(ListField, self).__init__(**kwargs)

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        return initial != data

    def clean(self, value):
        return value
