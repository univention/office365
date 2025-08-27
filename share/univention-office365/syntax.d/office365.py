# Office365 Azure AD Connection UDM syntax
#
# SPDX-FileCopyrightText: 2012-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

import univention.admin.localization
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

    empty_value = False
    choices = [
        ('Security Group', _('Security Group')),
        ('Microsoft 365 Group', _('Microsoft 365 Group')),
    ]


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
        # ('HiddenMembership', _('HiddenMembership')),
    ]
