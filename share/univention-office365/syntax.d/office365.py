# Office365 Azure AD Connection UDM syntax
#
# SPDX-FileCopyrightText: 2012-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

import univention.admin.localization
from univention.admin import configRegistry
from univention.admin.syntax import string, complex, UDM_Objects, select
import univention.admin.uexceptions


translation = univention.admin.localization.translation('univention-admin-handlers-office365')
_ = translation.translate


class Office365_User(UDM_Objects):
    udm_modules = ('users/user',)
    # TODO mdb_equality_candidates: (univentionOffice365Enabled) not indexed
    udm_filter = '(&(objectClass=univentionOffice365)(univentionOffice365Enabled=1)(univentionOffice365Data=*))'
    use_objects = False


class univentionOffice365ProfileSyntax(UDM_Objects):
    empty_value = True
    udm_modules = ('office365/profile',)
    key = 'dn'
    label = '%(name)s'
    udm_filter = '(objectClass=univentionOffice365Profile)'
    simple = True
    regex = None


class univentionOffice365ADConnection(UDM_Objects):
    empty_value = True
    udm_modules = ('office365/ad-connection',)
    key = '%(name)s'
    label = '%(name)s'
    udm_filter = '(objectClass=univentionOffice365ADConnection)'
    simple = True
    regex = None


class univentionOffice365ADConnections(complex):
    """
    Syntax for Azure AD connections

    >>> univentionOffice365ADConnections.parse(('defaultADconnection', 'dom1.user1@office365.dev-univention.de'))
    ['defaultADconnection', 'dom1.user1@office365.dev-univention.de']
    """

    subsyntaxes = (
        (_('Azure AD connection'), univentionOffice365ADConnection),
        (_('User Principal Name'), string),
    )
    subsyntax_names = ('AADConnection', 'userPrincipalName')
    all_required = True


class univentionMicrosoft365GroupType(select):
    """Syntax for selecting the azure group type."""

    education_feature_ucr = 'office365/education/enabled'
    udm_property_prefix = 'directory/manager/web/modules/groups/group/properties'
    education_attributes = (
        'UniventionMicrosoft365EducationClassCode',
        'UniventionMicrosoft365EducationClassGrade',
        'UniventionMicrosoft365EducationTermDisplayName',
        'UniventionMicrosoft365EducationTermExternalId',
        'UniventionMicrosoft365EducationTermStartDate',
        'UniventionMicrosoft365EducationTermEndDate',
    )
    empty_value = False
    choices = [
        ('Security Group', _('Security Group')),
        ('Microsoft 365 Group', _('Microsoft 365 Group')),
        ('Education Class', _('Education Class')),
    ]

    def __init__(self):
        # UDM creates the syntax before applying UCR-based layout overrides.
        # Refresh both choices and field visibility from the same feature flag.
        self._education_enabled()
        super().__init__()

    @classmethod
    def _education_enabled(cls):
        configRegistry.load()
        enabled = configRegistry.is_true(cls.education_feature_ucr)
        for attribute in cls.education_attributes:
            hidden_ucr = '%s/%s/__hidden' % (cls.udm_property_prefix, attribute)
            configRegistry[hidden_ucr] = str(not enabled).lower()
        return enabled

    @classmethod
    def _available_choices(cls):
        if cls._education_enabled():
            return cls.choices
        return [choice for choice in cls.choices if choice[0] != 'Education Group']

    @classmethod
    def get_choices(cls, lo, options):
        return cls.sort_choices(cls._available_choices())

    def get_widget_choices_options(self, udm_property):
        return {
            'staticValues': [
                {'id': choice_id, 'label': label}
                for choice_id, label in self._available_choices()
            ],
        }


class univentionMicrosoft365GroupVisibility(select):
    """
    https://git.knut.univention.de/univention/dev/projects/office365/-/issues/7
    https://learn.microsoft.com/en-us/graph/api/resources/group?view=graph-rest-1.0#group-visibility-options

    Note "empty_value = True" is nice in theory, but in practice this currently causes UMC to write the
    default value (of the extended attribute) when an object is created. But after creation one can modify
    the attribute and actually set the empty value (via UMC or udm modify --remove). But that is only
    nice for experiments, because in practical terms, UMC autoamtically selects and writes the default
    value unless explicitly un-selected on each modification of an object.
    """

    empty_value = True
    choices = [
        ('Private', _('Private')),
        ('Public', _('Public')),
        ('HiddenMembership', _('HiddenMembership')),
    ]
