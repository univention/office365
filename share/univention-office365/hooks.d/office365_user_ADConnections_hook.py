# -*- coding: utf-8 -*-
#
# Univention Microsoft 365 - UDM hook to access ADConnection data
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

import zlib
import json
import base64

from univention.admin.hook import simpleHook
import univention.admin.uexceptions
from univention.lib.i18n import Translation

_ = Translation('univention-admin-handlers-office365').translate
msg_require_mail = _('Microsoft 365 users must have a primary e-mail address specified.')
msg_require_owner = _('In order to create a Microsoft 365 team from a group, at least one group/team owner has to be specified.')
msg_force_group_type = _(
    "Warning: By changing the group type, the group will be deleted and recreated in Microsoft 365. This can affect the group's permissions and settings. If you want to continue anyway, please tick the 'Force group type' checkbox."
)


def decode_o365data(data):
    return json.loads(zlib.decompress(base64.b64decode(data.encode('ASCII'))))


def str2bool(val):
    try:
        return bool(int(val))
    except TypeError:
        # None
        return False


class Microsoft365GroupHook(simpleHook):
    type = 'Microsoft365GroupHook'

    def hook_ldap_pre_create(self, module):
        if str2bool(module.get('UniventionMicrosoft365Team')) and not module.get('UniventionMicrosoft365GroupOwners'):
            raise univention.admin.uexceptions.valueError(msg_require_owner)

    def hook_ldap_addlist(self, module, al=[]):
        al = [a for a in al if a[0] != 'dummyuniventionMicrosoft365ForceGroupType']
        return al

    def hook_ldap_pre_modify(self, module):
        if str2bool(module.get('UniventionMicrosoft365Team')) and not module.get('UniventionMicrosoft365GroupOwners'):
            raise univention.admin.uexceptions.valueError(msg_require_owner)
        if module.hasChanged('UniventionMicrosoft365GroupType') and not str2bool(module.get('UniventionMicrosoft365ForceGroupType')):
            has_been_synced = module.get('UniventionOffice365Data')
            group_type_is_set = module.oldinfo.get('UniventionMicrosoft365GroupType')
            changed_grouptype_to_default = module.descriptions['UniventionMicrosoft365GroupType'].base_default == module.get('UniventionMicrosoft365GroupType')

            if has_been_synced and (group_type_is_set or not changed_grouptype_to_default):
                raise univention.admin.uexceptions.valueError(msg_force_group_type)

    def hook_ldap_modlist(self, module, ml=[]):
        ml = [m for m in ml if m[0] != 'dummyuniventionMicrosoft365ForceGroupType']
        return ml


# Look into office365_user_ADConnections_hook.Office365ADConnectionsHook.hook_open to try to undrertand
# pre-version3 data structure for udm objects in office:
# pre_v3_data = {
# 	"UniventionOffice365ObjectID": '',
# 	'UniventionOffice365userPrincipalName': '',
#
# }
"""
Previous to version 3 the Office objects only could be related with one ADConnection.
"""
# v3_data = {
# 	'UniventionOffice365Data': 'office data encoded json in base64',  # information of the ad connections for this object
# 		"""{
# 		 			"ad connection name":
# 		 			{
# 		 				"userPrincipalName": "",
# 		 				"objectId": "",
# 		 			},...
# 		}"""
# 	'UniventionOffice365ADConnections': [("adConnectionName", "UserPrincipalName"),...],  # List of adconnections in which this object needs to be replicated
# 	'UniventionOffice365ADConnectionAlias': '',  #  current alias name of the AD connection
#
# }


class Office365ADConnectionsHook(simpleHook):
    type = 'Office365ADConnectionsHook'

    def hook_open(self, module):
        object_id = module.get('UniventionOffice365ObjectID')
        if object_id:
            # represent unmigrated object in new form
            upn = module.get('UniventionOffice365userPrincipalName', '')
            value = ('defaultADconnection', upn)
            module['UniventionOffice365ADConnections'] = [value]
            self.adconnection_data = {
                'defaultADconnection': {
                    'userPrincipalName': upn,
                    'objectId': object_id,
                }
            }
            return

        adconnection_data_encoded = module.get('UniventionOffice365Data')
        if adconnection_data_encoded:
            try:
                self.adconnection_data = decode_o365data(adconnection_data_encoded)
            except (zlib.error, TypeError):
                self.adconnection_data = {}
        else:
            self.adconnection_data = {}
        if not isinstance(self.adconnection_data, dict):
            self.adconnection_data = {}

        module['UniventionOffice365ADConnections'] = []
        adconnection_aliases = module.get('UniventionOffice365ADConnectionAlias', [])
        for adconnection in adconnection_aliases:
            try:
                upn = self.adconnection_data[adconnection]['userPrincipalName']
            except KeyError:
                upn = ''
            value = (adconnection, upn)
            module['UniventionOffice365ADConnections'].append(value)

    def hook_ldap_addlist(self, module, al=[]):
        al = [a for a in al if a[0] != 'dummyUniventionOffice365ADConnections']
        return al

    def hook_ldap_modlist(self, module, ml=[]):
        # remove virtual dummy attribute from modlist
        ml = [m for m in ml if m[0] != 'dummyUniventionOffice365ADConnections']

        if module.get('UniventionOffice365ObjectID'):
            # unmigrated object
            return ml
        if not module.hasChanged('UniventionOffice365ADConnections'):
            return ml

        adconnection_aliases_new = set(x for x, _ in module['UniventionOffice365ADConnections'])
        adconnections_old = module.oldinfo.get('UniventionOffice365ADConnections', [])
        adconnection_aliases_old = set(x for x, _ in adconnections_old)
        if adconnection_aliases_new == adconnection_aliases_old:
            return ml

        # Update the UniventionOffice365ADConnectionAlias list
        old = [x.encode('UTF-8') for x in module.get('UniventionOffice365ADConnectionAlias', [])]
        new = [x.encode('UTF-8') for x in adconnection_aliases_new]
        if new != old:
            ml.append(('univentionOffice365ADConnectionAlias', old, new))

        return ml

    def hook_ldap_pre_create(self, module):
        if str2bool(module.get('UniventionOffice365Enabled')) and not module.get('mailPrimaryAddress'):
            raise univention.admin.uexceptions.valueError(msg_require_mail)

    def hook_ldap_pre_modify(self, module):
        if str2bool(module.get('UniventionOffice365Enabled')) and not module.get('mailPrimaryAddress'):
            raise univention.admin.uexceptions.valueError(msg_require_mail)
