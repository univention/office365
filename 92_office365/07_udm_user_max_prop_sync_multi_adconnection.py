#!/usr/share/ucs-test/runner python
## -*- coding: utf-8 -*-
## desc: create user in azure, check property-sync with multi Azure AD connection support
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365


"""
This test is used to create user UDM, replicate in azure, check data attribute.
The next operations are performed on the two preconfigured connections to Azure:
- unset and set the needed UCR variables #TODO: why is it needed? Maybe it was prior to context managers?
- create UDM user
- wait for the user to be replicated in Azure
- retrieve the user from Azure and check the id
- compare all the properties of the user in UDM and Azure
"""
import time

import univention.testing.ucr as ucr_test
import univention.testing.udm as udm_test
import univention.testing.utils as utils
from univention.config_registry import handler_set, handler_unset

from helpers.office365_test_helpers import listener_attributes_data, udm_user_args, check_udm2azure_user, setup_logging, check_user_id_from_azure, azure_user_selection
from helpers.retry import retry_call
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.objects.azureobjects import UserAzure
from univention.office365.ucr_helper import UCRHelper

logger = setup_logging()
adconnection_aliases = UCRHelper.get_adconnection_aliases()
initialized_adconnections = [adconnection_alias for adconnection_alias in adconnection_aliases if AzureAccount(adconnection_alias).is_initialized()]

print("*** adconnection_aliases={!r}.".format(adconnection_aliases))
print("*** initialized_adconnections={!r}.".format(initialized_adconnections))


# TODO: The two context managers and the for loop for the adconnection_aliases are repeated almost all tests that involve UDM
with utils.AutomaticListenerRestart():
	with udm_test.UCSTestUDM() as udm:
		with ucr_test.UCSTestConfigRegistry() as ucr:
			ucr.load()

			for adconnection_alias in initialized_adconnections:
				print("*** Running for adconnection_alias={!r}.".format(adconnection_alias))

				core = MSGraphApiCore(AzureAccount(adconnection_alias))
				# ol = Office365Listener(_listener(), "ucs-test", listener_attributes_data, {}, "dn", adconnection_alias)

				print("*** Setting UCRs for maximum property sync...")
				to_unset = ["office365/attributes/anonymize", "office365/attributes/never",
					"office365/groups/sync", "office365/subscriptions/service_plan_names"]
				to_unset.extend([k.split("=")[0] for k, v in ucr.items() if k.startswith("office365/attributes/static/")])
				handler_unset(to_unset)
				handler_set([
					"office365/attributes/mapping/l=city",
					"office365/attributes/mapping/displayName=displayName",
					"office365/attributes/mapping/employeeType=jobTitle",
					"office365/attributes/mapping/givenName=givenName",
					"office365/attributes/mapping/mobile=mobilePhone",
					"office365/attributes/mapping/mail=otherMails",
					"office365/attributes/mapping/mailAlternativeAddress=otherMails",
					"office365/attributes/mapping/mailPrimaryAddress=otherMails",
					"office365/attributes/mapping/postalCode=postalCode",
					"office365/attributes/mapping/roomNumber=officeLocation",
					"office365/attributes/mapping/st=usageLocation",
					"office365/attributes/mapping/street=streetAddress",
					"office365/attributes/mapping/sn=surname",
					"office365/attributes/mapping/telephoneNumber=businessPhones",
					"office365/attributes/sync=l,st,displayName,employeeType,givenName,mailPrimaryAddress,mobile,mailAlternativeAddress,mail,postalCode,roomNumber,st,street,sn,telephoneNumber",
					"office365/debug/werror=yes",
				])
				utils.restart_listener()

				user_args = udm_user_args(ucr, minimal=False)
				user_args["set"]["UniventionOffice365Enabled"] = 1
				user_args["set"]["UniventionOffice365ADConnectionAlias"] = adconnection_alias

				print("*** Creating user with all possible properties...")
				user_dn, username = udm.create_user(check_for_drs_replication=True, **user_args)

				fail_msg = "User was not created properly (no O365Data->adconnection_alias->UniventionOffice365ObjectID)."
				user_id = retry_call(check_user_id_from_azure, fargs=[adconnection_alias, user_dn, fail_msg], tries=5, delay=2)

				print("*** Checking sync of all properties...")
				azure_user = UserAzure.get(core, user_id, selection=azure_user_selection)
				success, errors = check_udm2azure_user(user_args, azure_user, complete=True)
				if success:
					print("*** all attributes were synced correctly for adconnection_alias={!r}".format(adconnection_alias))
				else:
					utils.fail("One or more properties were not synced correctly:\n{}".format("\n".join(map(str, errors))))
			print("*** All went well for all in {!r}.".format(initialized_adconnections))
