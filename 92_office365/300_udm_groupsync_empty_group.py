#!/usr/share/ucs-test/runner python3
## -*- coding: utf-8 -*-
## desc: create users and sync their groups to azure
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365

"""
This test is used to check the user and group sync to Azure.
- Use both o365domain and azuretestdomain connections
- Set the UCR variable office365/groups/sync=yes
- Create a group in UDM
- Create a user in UDM with the group assigned and the UniventionOffice365Enabled=1 and the UniventionOffice365ADConnectionAlias=o365domain
- Check that the user in UDM is updated with the appropriate object id
- Check that the group in UDM is updated with the appropriate object id
- Get the group from azure
- List the members of the group and check that the user is in the list
- Repeat the same operation but with the other connection
- Check that no user or group is mixed created in the other connection
"""
import time

import univention.testing.strings as uts
import univention.testing.ucr as ucr_test
import univention.testing.udm as udm_test
import univention.testing.utils as utils
from helpers.office365_test_helpers import setup_logging, udm_user_args
from univention.config_registry import handler_set, handler_unset
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.exceptions import GraphRessourceNotFroundError
from univention.office365.microsoft.objects.azureobjects import GroupAzure
from univention.office365.ucr_helper import UCRHelper
from univention.office365.udmwrapper.udmobjects import (UDMOfficeGroup, UDMOfficeUser)

logger = setup_logging()
adconnection_aliases = UCRHelper.get_adconnection_aliases()
initialized_adconnections = [adconnection_alias for adconnection_alias in adconnection_aliases if AzureAccount(adconnection_alias).is_initialized()]
assert initialized_adconnections, "run ./01_initialize_external_testenv first!"

print("*** adconnection_aliases={!r}.".format(adconnection_aliases))
print("*** initialized_adconnections={!r}.".format(initialized_adconnections))

with utils.AutomaticListenerRestart():
	with udm_test.UCSTestUDM() as udm:
		with ucr_test.UCSTestConfigRegistry() as ucr:
			ucr.load()
			handler_set(["office365/groups/sync=yes"])
			utils.restart_listener()
			adconnection_alias = initialized_adconnections[0]
			print("*** adconnection_alias={!r}".format(adconnection_alias))
			core = MSGraphApiCore(AzureAccount(adconnection_alias))
			group_name = uts.random_name()
			description = uts.random_string()
			group_dn = udm.create_object(
				"groups/group",
				set=dict(
					name=group_name,
					description=description
				),
				position="cn=groups,{}".format(ucr.get("ldap/base")),
				check_for_drs_replication=True
			)

			print("*** Creating user with in group {!r} in adconnection_alias ({!r})...".format(group_name, adconnection_alias))
			users = {}
			members = 3
			for i in range(members):
				user_args = udm_user_args(ucr, minimal=True)
				print(user_args)
				user_args["set"]["UniventionOffice365Enabled"] = 1
				user_args["set"]["UniventionOffice365ADConnectionAlias"] = adconnection_alias
				user_args["set"]["groups"] = [group_dn]
				user_dn, username = udm.create_user(check_for_drs_replication=True, **user_args)
				users[user_dn] = username
			time.sleep(10)

			print("*** Checking that users were created (UniventionOffice365ObjectID in UDM object)...")
			azure_ids = {}
			for user_dn in users:
				user = UDMOfficeUser({}, None, dn=user_dn)
				with user.set_current_alias(adconnection_alias):
					azure_id = user.azure_object_id
				if not azure_id:
					utils.fail("User was not created properly (no UniventionOffice365ObjectID).")
				azure_ids[user_dn] = azure_id

			print("*** Checking that group was created (UniventionOffice365ObjectID in UDM object)...")
			udm_group1 = UDMOfficeGroup({}, None, dn=group_dn)
			with udm_group1.set_current_alias(adconnection_alias):
				group_objectid = udm_group1.azure_object_id
			if not group_objectid:
				utils.fail("Created group {!r} has no objectId in UDM Data object  ({!r}).".format(group_name, adconnection_alias))

			print("*** Checking that group was created in azure (list)...")
			try:
				azure_group = GroupAzure.get_by_name(core, group_name)
			except GraphRessourceNotFroundError:
				utils.fail("Created group {!r} cannot be retrieved from azure ({!r}).".format(group_name, adconnection_alias))

			print("*** Checking that users are in group...")
			member_objectids = azure_group.list_members_id()

			print(member_objectids)
			if not len(member_objectids) == members:
				utils.fail("Group {!r} does not contain exactly {!r} member ({!r}).".format(group_name, members, adconnection_alias))

			print(member_objectids)
			print(azure_ids.values())
			assert set(member_objectids) == set(azure_ids.values()), f'{group_name} does not contain all members'

			# remove all user one by one from the group
			for user_dn in users:
				udm.modify_object('groups/group', dn=group_dn, remove={'users': [user_dn]})
			time.sleep(10)

			# check group is in azure with no members
			azure_group = GroupAzure.get(core, group_objectid)
			member_objectids = azure_group.list_members_id()
			assert len(member_objectids) == 0, f'group is not empty {member_objectids}'
			assert 'ZZZ_deleted' in azure_group.displayName, azure_group

			print("*** All went well.")

# Cleanup
to_unset = ["office365/groups/sync"]
handler_unset(to_unset)
utils.restart_listener()
