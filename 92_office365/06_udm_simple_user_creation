#!/usr/share/ucs-test/runner python
## -*- coding: utf-8 -*-
## desc: create user UDM, replicate in azure, check data attribute
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365


"""
This test is used to create user UDM, replicate in azure, check data attribute.
The next operations are performed on the two preconfigured connections to Azure:
- create UDM user
- wait for the user to be replicated in Azure
- retrieve the user from Azure and check the id
"""
import time

import univention.testing.ucr as ucr_test
import univention.testing.udm as udm_test
import univention.testing.utils as utils

from helpers.office365_test_helpers import listener_attributes_data, udm_user_args, setup_logging, check_user_id_from_azure
from helpers.retry import retry_call
from univention.office365.microsoft.account import AzureAccount
from univention.office365.ucr_helper import UCRHelper

logger = setup_logging()
adconnection_aliases = UCRHelper.get_adconnection_aliases()
initialized_adconnections = [adconnection_alias for adconnection_alias in adconnection_aliases if AzureAccount(adconnection_alias).is_initialized()]

print("*** adconnection_aliases={!r}.".format(adconnection_aliases))
print("*** initialized_adconnections={!r}.".format(initialized_adconnections))

with utils.AutomaticListenerRestart():
	with udm_test.UCSTestUDM() as udm:
		with ucr_test.UCSTestConfigRegistry() as ucr:
			ucr.load()

			# TODO: Move to an assert before the context managers
			if not initialized_adconnections:
				utils.fail("No configured AD connection, can not start test!")

			for adconnection_alias in initialized_adconnections:
				print("*** Running for adconnection_alias={!r}.".format(adconnection_alias))

				user_args = udm_user_args(ucr, minimal=False)
				user_args["set"]["UniventionOffice365Enabled"] = 1
				user_args["set"]["UniventionOffice365ADConnectionAlias"] = adconnection_alias

				print("*** Creating user with all possible properties...")
				user_dn, username = udm.create_user(check_for_drs_replication=True, **user_args)

				fail_msg = "User was not created properly (no UniventionOffice365ObjectID)."
				user_id = retry_call(check_user_id_from_azure, fargs=[adconnection_alias, user_dn, fail_msg], tries=5, delay=2)

			print("*** All went well for all in {!r}.".format(initialized_adconnections))
