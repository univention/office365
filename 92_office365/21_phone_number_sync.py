#!/usr/share/ucs-test/runner pytest-3 -s -l -vv
## -*- coding: utf-8 -*-
## desc: create user UDM, replicate in azure, check data attribute
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365

import time
import pytest

import univention.testing.strings as uts

from helpers.office365_test_helpers import udm_user_args, check_user_id_from_azure, azure_user_selection, o365_connection, azuretestdomain
from helpers.retry import retry_call
import univention.testing.utils as utils

from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.objects.azureobjects import UserAzure
from univention.office365.ucr_helper import UCRHelper


class Test_UDMUserCreation2:
	@pytest.mark.parametrize('adconnection_alias, adconnection_srcpath', [o365_connection, azuretestdomain], indirect=True)
	def test_udm_simple_user_creation(self, udm, ucr, restart_listener_after_test, adconnection, adconnection_alias):
		"""
		The azure Attributes: mobilePhone and businessPhone exibit weird behaviour regarding update and Delete
		"""

		core = MSGraphApiCore(AzureAccount(adconnection_alias))
		# TODO: repeated. Needed? Join.
		print("*** Setting UCRs for maximum property sync...")
		to_unset = ["office365/attributes/anonymize", "office365/attributes/never",
			"office365/groups/sync", "office365/subscriptions/service_plan_names"]
		to_unset.extend([k.split("=")[0] for k, v in ucr.items() if k.startswith("office365/attributes/static/")])
		ucr.handler_unset(to_unset)
		ucr.handler_set([
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

		udm_create_list = udm_user_args(ucr, minimal=True)
		udm_create_list["set"]["UniventionOffice365Enabled"] = 1
		udm_create_list["set"]["UniventionOffice365ADConnectionAlias"] = adconnection_alias

		udm_modlist = {"set": {
			"phone": 12 * uts.random_int(),
			"mobileTelephoneNumber": uts.random_string()
		}}

		udm_removelist = {"set": {
			"phone": "",
			"mobileTelephoneNumber": ""
		}}

		print("*** Creating user with some properties...")
		user_dn, username = udm.create_user(check_for_drs_replication=True, **udm_create_list)

		user_id = retry_call(check_user_id_from_azure, fargs=[adconnection_alias, user_dn], tries=12, delay=5)

		print("*** Modifying phone properties")
		udm.modify_object(modulename="users/user", dn=user_dn, **udm_modlist)
		time.sleep(10)

		azure_user = UserAzure.get(core, user_id, selection=azure_user_selection)

		print("*** Checking sync of properties #1...")
		assert azure_user.businessPhones == udm_modlist["set"]["phone"]
		assert azure_user.mobilePhone == udm_modlist["set"]["mobileTelephoneNumber"]

		udm.modify_object(modulename="users/user", dn=user_dn, **udm_removelist)
		time.sleep(10)

		azure_user = UserAzure.get(core, user_id, selection=azure_user_selection)

		# TODO: what is the default value of azure objects if nothing is returned by MSGraph
		assert not azure_user.businessPhones
		assert not azure_user.mobilePhone
