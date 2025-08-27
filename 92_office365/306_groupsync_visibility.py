#!/usr/share/ucs-test/runner python3
## -*- coding: utf-8 -*-
## desc: test group visibility sync to azure
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365

"""
This test is used to check the group visibility sync to Azure.
"""

import time
import copy

import univention.testing.strings as uts
import univention.testing.ucr as ucr_test
import univention.testing.udm as udm_test
import univention.testing.utils as utils
from univention.config_registry import handler_set, handler_unset

from helpers.office365_test_helpers import listener_attributes_data, udm_user_args, check_udm2azure_user, setup_logging, check_group_visibility
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.exceptions import GraphRessourceNotFroundError
from univention.office365.microsoft.objects.azureobjects import GroupAzure
from univention.office365.ucr_helper import UCRHelper
from univention.office365.udmwrapper.udmobjects import UDMOfficeUser, UDMOfficeGroup, GroupType

logger = setup_logging()
adconnection_aliases = UCRHelper.get_adconnection_aliases()
initialized_adconnections = [adconnection_alias for adconnection_alias in adconnection_aliases if AzureAccount(adconnection_alias).is_initialized()]
assert initialized_adconnections, 'run ./01_initialize_external_testenv first!'

print('*** adconnection_aliases={!r}.'.format(adconnection_aliases))
print('*** initialized_adconnections={!r}.'.format(initialized_adconnections))


with utils.AutomaticListenerRestart():
    with udm_test.UCSTestUDM() as udm:
        with ucr_test.UCSTestConfigRegistry() as ucr:
            ucr.load()

            handler_set(['office365/groups/sync=yes'])
            utils.restart_listener()

            adconnection_alias1 = initialized_adconnections[0]
            print('*** adconnection_alias1={!r}'.format(adconnection_alias1))
            core_1 = MSGraphApiCore(AzureAccount(adconnection_alias1))

            # test create grouptypes with specific visibility
            for groupconf in (
                dict(UniventionMicrosoft365GroupType=GroupType.M365.value, UniventionMicrosoft365GroupVisibility="Private"),
                dict(UniventionMicrosoft365GroupType=GroupType.M365.value, UniventionMicrosoft365GroupVisibility="Public"),
                dict(UniventionMicrosoft365GroupType=GroupType.M365.value),
                dict(UniventionMicrosoft365GroupType=GroupType.SECURITY.value, UniventionMicrosoft365GroupVisibility="Private"),
                dict(UniventionMicrosoft365GroupType=GroupType.SECURITY.value, UniventionMicrosoft365GroupVisibility="Public"),
                dict(UniventionMicrosoft365GroupType=GroupType.SECURITY.value)
            ):
                user_args = udm_user_args(ucr, minimal=True)
                user_args['set']['UniventionOffice365Enabled'] = 1
                user_args['set']['UniventionOffice365ADConnectionAlias'] = adconnection_alias1

                group_name = uts.random_name()
                description = uts.random_string()
                group_dn = udm.create_object(
                    'groups/group', set=dict(name=group_name, description=description) | groupconf, position='cn=groups,{}'.format(ucr.get('ldap/base')), check_for_drs_replication=True
                )

                print('*** Creating user with in group {!r} in adconnection_alias1 ({!r})...'.format(group_name, adconnection_alias1))
                user_args['set']['primaryGroup'] = group_dn
                user_dn, username = udm.create_user(check_for_drs_replication=True, **user_args)
                time.sleep(10)

                print('*** Checking that user was created (UniventionOffice365ObjectID in UDM object)...')
                udm_user_one = UDMOfficeUser({}, None, dn=user_dn)
                with udm_user_one.set_current_alias(adconnection_alias1):
                    azure_user_id_one = udm_user_one.azure_object_id
                if not azure_user_id_one:
                    utils.fail('User was not created properly (no UniventionOffice365ObjectID).')

                print('*** Checking that group was created (UniventionOffice365ObjectID in UDM object)...')
                udm_group1 = UDMOfficeGroup({}, None, dn=group_dn)
                with udm_group1.set_current_alias(adconnection_alias1):
                    group_objectid = udm_group1.azure_object_id
                if not group_objectid:
                    utils.fail('Created group {!r} has no objectId in UDM Data object  ({!r}).'.format(group_name, adconnection_alias1))

                assert check_group_visibility(core_1, group_name, groupconf.get("UniventionMicrosoft365GroupVisibility", None)), 'Group visibility in Azure does not match the expected visibility'



# Cleanup
to_unset = ['office365/groups/sync']
handler_unset(to_unset)
utils.restart_listener()
