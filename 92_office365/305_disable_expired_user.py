#!/usr/share/ucs-test/runner python3
## -*- coding: utf-8 -*-
## desc: test account deactivation after expiration
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365

"""
This test is used to test account deactivation
if a user is expired via a cronjob
"""
import random

import univention.testing.ucr as ucr_test
import univention.testing.udm as udm_test
import univention.testing.utils as utils

from helpers.office365_test_helpers import udm_user_args, check_user_id_from_azure, azure_user_disabled, azure_user_enabled, azure_user_selection
from helpers.retry import retry_call
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.objects.azureobjects import UserAzure
from univention.office365.ucr_helper import UCRHelper
import subprocess


adconnection_aliases = UCRHelper.get_adconnection_aliases()
initialized_adconnections = [adconnection_alias for adconnection_alias in adconnection_aliases if AzureAccount(adconnection_alias).is_initialized()]


# Create function and parametrize
with utils.AutomaticListenerRestart():
	with udm_test.UCSTestUDM() as udm:
		with ucr_test.UCSTestConfigRegistry() as ucr:
			ucr.load()
			#
			# Only test one connection, not all...
			adconnection_alias = random.choice(initialized_adconnections)

			core = MSGraphApiCore(AzureAccount(adconnection_alias))

			user_args = udm_user_args(ucr, minimal=True)
			user_args["set"]["UniventionOffice365Enabled"] = 1
			user_args["set"]["UniventionOffice365ADConnectionAlias"] = adconnection_alias

			print("*** Creating user...")
			user_dn, username = udm.create_user(check_for_drs_replication=True, **user_args)
			print("*** Checking sync of properties...")
			user_id = retry_call(check_user_id_from_azure, fargs=[adconnection_alias, user_dn], tries=6, delay=5)
			azure_user = UserAzure.get(core, user_id, selection=azure_user_selection)

			print("*** Expiring user..")
			udm.modify_object(modulename="users/user", dn=user_dn, set={"userexpiry": "1999-01-01"})
			azure_user = retry_call(azure_user_disabled, fargs=[core, user_id], tries=6, delay=5)
			print("*** Enabling user in Azure..")
			core.modify_user(user_id, {"accountEnabled": True})
			azure_user = retry_call(azure_user_enabled, fargs=[core, user_id], tries=6, delay=5)
			print("*** Running cronjob..")
			subprocess.check_output(['/usr/share/univention-office365/scripts/o365_disable_expired_users', '-m'])
			print("*** Waiting for user to be disabled again..")
			azure_user = retry_call(azure_user_disabled, fargs=[core, user_id], tries=6, delay=5)
			print("*** All tests succeeded.")
			print("*** All went well.")
