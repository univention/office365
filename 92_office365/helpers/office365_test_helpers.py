"""
Common functions used by tests.
"""
# Copyright 2016-2021 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.

from __future__ import print_function
import random
import pprint
import base64
import logging
import os
import shutil
import pwd
import sys
import time
import subprocess
from datetime import datetime
from operator import itemgetter
from types import TracebackType

import six
import univention.admin.syntax as udm_syntax
import univention.testing.strings as uts
import univention.testing.utils as utils
from typing import Any, Dict, List, Type, Union, Tuple, Optional

from univention.config_registry import handler_set

# from univention.office365.azure_handler import ResourceNotFoundError
# from univention.office365.azure_auth import AzureAuth, AzureADConnectionHandler

from univention.office365.connector.account_connector import AccountConnector
from univention.office365.logging2udebug import get_logger, LevelDependentFormatter
# from univention.office365.api.exceptions import GraphError
# from univention.office365.listener import Office365Listener
from univention.office365.microsoft.account import AzureAccount

from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError
from univention.office365.microsoft.objects.azureobjects import AzureObject, GroupAzure, UserAzure, TeamAzure
from univention.office365.udm_helper import UDMHelper
from univention.office365.udmwrapper.udmobjects import UDMOfficeUser, UniventionOffice365Data
from univention.office365.utils.utils import create_random_pw

udm_syntax.update_choices()
blacklisted_ul = ["SD", "SY", "KP", "CU", "IR"]  # some usageLocations are not valid (https://www.microsoft.com/en-us/microsoft-365/business/microsoft-office-license-restrictions), collecting them here
usage_locations_code = list(set(x[0] for x in udm_syntax.Country.choices) - set(blacklisted_ul))

azure_user_selection = ["assignedLicenses",
				 "otherMails",
				 "businessPhones",
				 "displayName",
				 "givenName",
				 "jobTitle",
				 "mail",
				 "mobilePhone",
				 "officeLocation",
				 "preferredLanguage",
				 "surname",
				 "userPrincipalName",
				 "id",
				 "accountEnabled",
				 "onPremisesImmutableId",
				 "mailNickname",
				 "city",
				 "usageLocation",
				 "postalCode",
				 "streetAddress",
				 "assignedPlans"
				]

udm2azure = dict(
	firstname=lambda x: x.givenName,
	lastname=lambda x: x.surname,
	set=dict(
		city=lambda x: x.city,
		country=lambda x: x.usageLocation,
		displayName=lambda x: x.displayName,
		employeeType=lambda x: x.jobTitle,
		mailPrimaryAddress=lambda x: x.otherMails,
		postcode=lambda x: x.postalCode,
		roomNumber=lambda x: x.officeLocation,
		street=lambda x: x.streetAddress
	),
	append=dict(
		mailAlternativeAddress=lambda x: x.otherMails,
		mobileTelephoneNumber=lambda x: x.mobilePhone,
		phone=lambda x: x.businessPhones,
	)
)
udm2azure["append"]["e-mail"] = lambda x: x.otherMails

listener_attributes_data = dict(
	anonymize=[],
	listener=[
		"city", "displayName", "e-mail", "employeeType", "givenName", "jpegPhoto", "mailAlternativeAddress",
		"mailPrimaryAddress", "mobile", "postalCode", "roomNumber", "sn", "st", "street", "telephoneNumber",
		"univentionOffice365Enabled"
	],
	mapping=dict(
		city="city",
		displayName="displayName",
		employeeType="jobTitle",
		givenName="givenName",
		mail="otherMails",
		mailAlternativeAddress="otherMails",
		mailPrimaryAddress="mail",
		mobile="mobilePhone",
		postalCode="postalCode",
		roomNumber="officeLocation",
		sn="surname",
		st="usageLocation",
		street="streetAddress",
		telephoneNumber="businessPhones",
	),
	never=set(),
	static=[],
	sync=[
		"city", "displayName", "e-mail", "employeeType", "givenName", "jpegPhoto", "mailAlternativeAddress",
		"mailPrimaryAddress", "mobile", "postalCode", "roomNumber", "sn", "st", "st", "street", "telephoneNumber"
	]
)


class AzureDirectoryTestObjects(object):
	def __init__(self, otype, core, azure_objects=None):
		# type: (str, MSGraphApiCore, List[AzureObject]) -> None
		"""
		Context manager that deletes the azure objects when leaving it.
		:param otype: str: type of object to delete ("user", "group")
		:param a_handler: AzureHandler object
		:param obj_ids: list of object IDs to delete from azure when leaving
		the context manager
		"""
		assert otype in ["user", "group"]
		self._otype = otype
		self._otype_cls = UserAzure if otype == "user" else GroupAzure
		assert isinstance(azure_objects, list)
		self._azure_objects = azure_objects
		self._core = core

	def __enter__(self):
		# type: () -> AzureDirectoryTestObjects
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		# type: (Type, Exception, TracebackType) -> None
		if not self._core:
			return
		for azure_object in self._azure_objects:
			print(">>> Deleting test-{} '{}'...".format(self._otype, azure_object.id))
			try:
				azure_object.set_core(self._core)
				azure_object.deactivate(rename=True)
			except MSGraphError:
				print(">>> OK: Doesn't exist (anymore): {} '{}'.".format(self._otype, azure_object.id))
				continue

			if isinstance(azure_object, UserAzure) and azure_object.accountEnabled:
				print(">>> Fail: could not delete test-{} '{}': {}".format(self._otype, azure_object.id, azure_object))
			else:
				print(">>> OK: deactivated test-{} '{}'.".format(self._otype, azure_object.id))


class AzureDirectoryTestUsers(AzureDirectoryTestObjects):
	def __init__(self, core, azure_objects=None):
		# type: (MSGraphApiCore, List[UserAzure]) -> None
		"""
		Context manager that deletes the azure users when leaving it.
		:param a_handler: AzureHandler object
		:param user_ids: list of user IDs to delete from azure
		when leaving the context manager
		"""
		super(AzureDirectoryTestUsers, self).__init__("user", core, azure_objects)


class AzureDirectoryTestGroups(AzureDirectoryTestObjects):
	def __init__(self, core, azure_objects=None):
		# type: (MSGraphApiCore, List[GroupAzure]) -> None
		"""
		Context manager that deletes the azure groups when leaving it.
		:param a_handler: AzureHandler object
		:param group_ids: list of group IDs to delete from azure
		when leaving the context manager
		"""
		super(AzureDirectoryTestGroups, self).__init__("group", core, azure_objects)


def print_users(users, complete=False, short=False):
	# type: (Union[List[UserAzure], UserAzure], bool, bool) -> None
	if not users:
		print("None.")
		return
	if isinstance(users, UserAzure):
		users = [users]
	elif isinstance(users, list):
		users = users
	for user in users:
		assert isinstance(user, UserAzure)
		print(u"objectType: {0} objectId: {1} accountEnabled: {2} displayName: '{3}'".format(
			"user",
			user.id,
			user.accountEnabled,
			user.displayName)
		)
		if short:
			pass
		elif complete:
			pprint.pprint(user)
			print("")
		else:
			for attr in ["accountEnabled", "displayName", "mail", "odata.type", "otherMails", "userPrincipalName"]:
				if hasattr(user, attr):
					print(u"      {0}: {1}".format(attr, getattr(user, attr)))
				else:
					print("      no attr {0}".format(attr))
			print("      assignedPlans:")
			for plan in user.assignedPlans:
				print(u"            service: {0} \t capabilityStatus: {1}".format(
					plan["service"],
					plan["capabilityStatus"]
				))
			if not user.assignedPlans:
				print("            None")
			print("      provisionedPlans:")
			for plan in user.provisionedPlans:
				print(u"            service: {0} \t capabilityStatus: {1} \t provisioningStatus: {2}".format(
					plan["service"],
					plan["capabilityStatus"],
					plan["provisioningStatus"]
				))
			if not user.provisionedPlans:
				print("            None")


def azure_group_args():
	name = "{} {}".format(uts.random_username(), uts.random_username())
	return dict(
		description=uts.random_string(),
		displayName=name,
		mailEnabled=False,
		mailNickname=name.replace(" ", "_-_"),
		securityEnabled=True
	)


def azure_user_args(core, minimal=True):
	# type: (MSGraphApiCore, bool) -> Dict[str, Any]
	local_part_email = uts.random_username()
	domains = core.list_verified_domains()["value"]
	assert len(domains) > 0, "Verified domains is empty"
	domain = domains[0]["id"]
	res = dict(
		accountEnabled=True,
		displayName=uts.random_string(),
		onPremisesImmutableId=base64.b64encode(uts.random_string()) if six.PY2 else base64.b64encode(uts.random_string().encode("UTF-8")).decode("ASCII"),
		mailNickname=local_part_email,
		passwordProfile=dict(
			password=create_random_pw(),
			forceChangePasswordNextSignInWithMfa=False
		),
		userPrincipalName="{0}@{1}".format(local_part_email, domain)
	)
	if not minimal:
		res.update(dict(
			city=uts.random_string(),
			country=random.choice(usage_locations_code),
			givenName=uts.random_string(),
			jobTitle=uts.random_string(),
			otherMails=[
				"{}@{}".format(uts.random_string(), uts.random_string()),
				"{}@{}".format(uts.random_string(), uts.random_string())
			],
			mobile=uts.random_string(),
			postalCode=uts.random_string(),
			officeLocation=uts.random_string(),
			usageLocation=random.choice(usage_locations_code),
			streetAddress=uts.random_string(),
			surname=uts.random_string(),
			businessPhones=uts.random_string(),
		))
	return res


def udm_user_args(ucr, minimal=True, sufix=""):
	_username = uts.random_username() + sufix
	res = dict(
		firstname=uts.random_string() + sufix,
		lastname=uts.random_string() + sufix,
		username=_username,
		set=dict(
			displayName=_username,
			password=uts.random_string(),
			mailHomeServer="{}.{}".format(ucr["hostname"], ucr["domainname"]),
			mailPrimaryAddress="{}@{}".format(_username, ucr["domainname"]),
		)
	)
	res["append"] = dict()
	if not minimal:
		res["set"].update(dict(
			birthday="19{}-0{}-{}{}".format(
				2 * uts.random_int(),
				uts.random_int(1, 9),
				uts.random_int(0, 2),
				uts.random_int(1)
			),
			city=uts.random_string(),
			country=random.choice(usage_locations_code),
			departmentNumber=uts.random_string(),
			description=uts.random_string(),
			employeeNumber=3 * uts.random_int(),
			employeeType=uts.random_string(),
			organisation=uts.random_string(),
			postcode=3 * uts.random_int(),
			roomNumber=3 * uts.random_int(),
			street=uts.random_string(),
			title=uts.random_string()
		))
		res["append"].update(dict(
			homePostalAddress=[
				'"{}" "{}" "{}"'.format(uts.random_string(), uts.random_string(), uts.random_string()),
				'"{}" "{}" "{}"'.format(uts.random_string(), uts.random_string(), uts.random_string())
			],
			homeTelephoneNumber=[uts.random_string(), uts.random_string()],
			mailAlternativeAddress=[
				"{}@{}".format(uts.random_username(), ucr["domainname"]),
				"{}@{}".format(uts.random_username(), ucr["domainname"])
			],
			mobileTelephoneNumber=[uts.random_string(), uts.random_string()],
			pagerTelephoneNumber=[uts.random_string(), uts.random_string()],
			phone=[12 * uts.random_int(), 12 * uts.random_int()],
			secretary=[
				"uid=Administrator,cn=users,{}".format(ucr["ldap/base"]),
				"uid=Guest,cn=users,{}".format(ucr["ldap/base"])
			]
		))
		# func arg name with '-' not allowed
		res["append"]["e-mail"] = [
			"{}@{}".format(uts.random_username(), uts.random_username()),
			"{}@{}".format(uts.random_username(), uts.random_username())
		]
	return res


def create_team(udm, ucr, owner_dn=None, users=None):
	if users is None:
		users = []
	group_args = dict(
		name=uts.random_string(),
		position="cn=groups,{}".format(ucr.get("ldap/base")),
		set=dict(
			description="ucstest",
			users=users,
			UniventionMicrosoft365Team=1,
			UniventionMicrosoft365GroupOwners=owner_dn,),
	)

	return udm.create_group(check_for_drs_replication=True, **group_args)


def create_team_member(udm, ucr, alias, group_dn=None):
	user_args = udm_user_args(ucr)
	user_args["set"]["UniventionOffice365Enabled"] = 1
	user_args["set"]["UniventionOffice365ADConnectionAlias"] = [alias]
	if group_dn:
		user_args["set"]["groups"] = group_dn

	return udm.create_user(check_for_drs_replication=True, **user_args)


def check_udm2azure_user(udm_args, azure_user, complete=True):
	# type: (Dict[str, Any], UserAzure, bool) -> Tuple[bool, List[Tuple[str,str,str]]]
	res = list()
	fail = False
	for k, from_azure in [("firstname", udm2azure["firstname"]), ("lastname", udm2azure["lastname"])]:
		try:
			udm_value = udm_args[k]
		except KeyError:
			if complete:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			continue
		azure_value = from_azure(azure_user)
		if udm_value != azure_value:
			fail = True
			res.append((k, udm_value, azure_value))

	for k, from_azure in udm2azure["set"].items():
		try:
			udm_value = udm_args["set"][k]
		except KeyError:
			if complete:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			continue
		try:
			azure_value = from_azure(azure_user)
		except KeyError:
			fail = True
			res.append((k, "value was not set", "cannot compare"))
			continue
		if isinstance(azure_value, list):
			tmp_ok = udm_value in azure_value
		else:
			tmp_ok = udm_value == azure_value
		if not tmp_ok:
			fail = True
			res.append((k, udm_value, azure_value))

	for k, from_azure in udm2azure["append"].items():
		try:
			udm_values = udm_args["append"][k]
		except KeyError:
			if complete:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			continue
		azure_values = from_azure(azure_user)
		if k == "phone":
			if len(udm_value) == 0:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			if all([x not in udm_values for x in azure_values]):
				fail = True
				res.append((k, udm_value, azure_values))
		elif k == "mobileTelephoneNumber":
			if azure_values not in udm_values:
				fail = True
				res.append((k, udm_value, azure_values))
		else:
			for udm_value in udm_values:
				if k == "homePostalAddress":
					udm_value = udm_value.replace('"', '').replace(" ", "$")

				if azure_values and udm_value not in azure_values:
					fail = True
					res.append((k, udm_value, azure_values))
	return not fail, res


def setup_logging():
	logger = get_logger("office365", "o365")
	handler = logging.StreamHandler()
	handler.setLevel(logging.DEBUG)
	handler.setFormatter(LevelDependentFormatter())
	logger.addHandler(handler)
	logger.setLevel(logging.DEBUG)
	return logger


def setup_externally_configured_adconnections(logger):
	try:
		# TODO: Move the path to an external config file
		if not os.path.exists("/etc/univention-office365/o365domain"):
			AccountConnector.create_new_adconnection(logger, "o365domain", restart_listener=False)
		account = AzureAccount("o365domain", lazy_load=True)
		if not account.is_initialized():
			newconf_dir = account.conf_dirs.get("CONFDIR")
			srcpath = "/etc/univention-office365/o365-dev-univention-de"
			shutil.rmtree(newconf_dir, ignore_errors=True)
			shutil.copytree(srcpath, newconf_dir)
			ucrv_set = 'office365/adconnection/alias/o365domain=initialized'
			handler_set([ucrv_set])

		if not os.path.exists("/etc/univention-office365/azuretestdomain"):
			AccountConnector.create_new_adconnection(logger, "azuretestdomain", restart_listener=False)
		account = AzureAccount("azuretestdomain", lazy_load=True)
		if not account.is_initialized():
			newconf_dir = account.conf_dirs.get("CONFDIR")
			srcpath = "/etc/univention-office365/u-azure-test-de"
			shutil.rmtree(newconf_dir, ignore_errors=True)
			shutil.copytree(srcpath, newconf_dir)
			ucrv_set = 'office365/adconnection/alias/azuretestdomain=initialized'
			handler_set([ucrv_set])

		# TODO: Move the path to an external config file
		for root, dirs, files in os.walk("/etc/univention-office365"):
			for d in dirs:
				os.chown(os.path.join(root, d), pwd.getpwnam('listener').pw_uid, 0)
			for f in files:
				os.chown(os.path.join(root, f), pwd.getpwnam('listener').pw_uid, 0)
		subprocess.call(["service", "univention-directory-listener", "restart"])
	except Exception:
		import traceback
		print(traceback.format_exc())
		return False

	return True


def remove_externally_configured_adconnections(logger):
	account = AzureAccount("o365domain")
	account_connector = AccountConnector(logger)
	if account.is_initialized():
		account_connector.remove_adconnection("o365domain")
	account = AzureAccount("azuretestdomain")
	if account.is_initialized():
		account_connector.remove_adconnection("azuretestdomain")
	return True


def wait_for_seconds(func):
	def wrapper(*args, **kwargs):
		wait_for_seconds = kwargs.pop("wait_for_seconds", 500)
		wait_interval = kwargs.pop("wait_interval", 1)
		start = datetime.now()
		now = datetime.now()
		# print(func.func_doc)
		while (now - start).total_seconds() < wait_for_seconds:
			ret = func(*args, **kwargs)
			if ret:
				print("Success, this took %d seconds" % ((now - start).total_seconds(),))
				return ret
			print(".", end=' ')
			sys.stdout.flush()
			time.sleep(wait_interval)
			now = datetime.now()
		else:
			raise Exception("No success in %d seconds" % (wait_for_seconds,))
	return wrapper


@wait_for_seconds
def check_team_owner(core, team_id, owner_name):
	# type: (MSGraphApiCore, str, str) -> bool
	''' Checking if Team Owner is set to the correct user'''
	try:
		team_members = core.list_team_members(team_id)
	except MSGraphError:
		return False

	for member in team_members['value']:
		if member['displayName'] == owner_name and 'owner' in member['roles']:
			return member
	return False


@wait_for_seconds
def check_team_members(core, team_id, member_count):
	# type: (MSGraphApiCore, str, int) -> Union[bool, Dict[str, Any]]
	''' Checking if the correct number of Team members is set'''
	try:
		team_members = core.list_team_members(team_id)
		if team_members['@odata.count'] == member_count:
			return team_members
	except MSGraphError:
		return False


@wait_for_seconds
def check_member_of(azure_user, group_id):
	# type: (UserAzure, str) -> Union[bool, Dict[str, Any]]
	''' Checking if group_id in member_of'''
	try:
		member_of = azure_user.member_of(ids_only=True)
		if group_id in member_of:
			return True
	except MSGraphError:
		return False

@wait_for_seconds
def check_team_created(core, group_name):
	# type: (MSGraphApiCore, str) -> Optional[GroupAzure]
	''' Checking if Group is created and converted to a Team'''
	teams = TeamAzure.list(core)
	for team in teams:
		if team.displayName == group_name:
			return team
	else:
		return None


@wait_for_seconds
def check_group_created(core, group_name):
	# type: (MSGraphApiCore, str) -> Optional[GroupAzure]
	''' Checking if Group is created and converted to a Team'''
	groups = GroupAzure.list(core)
	for group in groups:
		if group.displayName == group_name:
			return group
	else:
		return None


@wait_for_seconds
def check_team_archived(core, group_name):
	# type: (MSGraphApiCore, str) -> bool
	''' Checking if Team is removed'''
	teams = TeamAzure.list(core)
	for team in teams:
		if team.displayName == group_name:
			return False
	else:
		return True


@wait_for_seconds
def check_user_office365_data_updated(user_dn):
	# type: (str) -> bool
	''' Checking if Office365Data is updated'''
	if UDMOfficeUser({}, None, user_dn).azure_data:
		return True
	else:
		return False


def check_user_location(office_listener, user_id, ucr_usageLocation, fail_msg):
	azure_user = office_listener.ah.list_users(objectid=user_id)
	if not azure_user["usageLocation"] == ucr_usageLocation:
		utils.fail(fail_msg.format(
			azure_user["usageLocation"], ucr_usageLocation))
	return azure_user


def check_user_id_from_azure(adconnection_alias, user_dn, fail_msg=None):
	fail_msg = fail_msg or "User was not created properly (no UniventionOffice365ObjectID)."
	print("*** Checking that user was created (UniventionOffice365ObjectID in UDM object)...")
	udm_user = UDMOfficeUser({}, None, dn=user_dn)
	with udm_user.set_current_alias(adconnection_alias):
		user_id = udm_user.azure_object_id
	if not user_id:
		utils.fail(fail_msg)
	return user_id


def check_user_in_group_from_azure(udm, group_dn, user_dn):
	# type: (UDMHelper, str, str) -> "user.User"
	print("*** Checking that user was created (UniventionOffice365ObjectID in UDM object)...")
	udm_user = udm.get_udm_user(user_dn)
	if udm_user['groups'] != [group_dn]:
		utils.fail("User has groups: %r, expected %r." % (udm_user['groups'], [group_dn]))
	return udm_user


def __is_azure_user_enabled(azure_user):
	print_users(azure_user, short=True)
	return azure_user.accountEnabled


def azure_user_disabled(core, user_id):
	# type: (MSGraphApiCore, str) -> UserAzure
	azure_user = UserAzure.get(core, user_id, selection=azure_user_selection)
	if __is_azure_user_enabled(azure_user):
		utils.fail("Account was not deactivated.")
	return azure_user


def azure_user_enabled(core, user_id):
	# type: (MSGraphApiCore, str) -> UserAzure
	azure_user = UserAzure.get(core, user_id, selection=azure_user_selection)
	if not __is_azure_user_enabled(azure_user):
		utils.fail("Account was not activated.")
	return azure_user


def check_azure_user_change(core, user_id, attribute_name, attribute_value):
	# type: (MSGraphApiCore, str, str, Any) -> None
	print("*** Checking value of usageLocation...")
	azure_user = UserAzure.get(core, user_id, selection=azure_user_selection)
	if getattr(azure_user, attribute_name) != attribute_value:
		utils.fail("'{}' was not correctly set (is: {}, should be: {}).".format(
			attribute_name, getattr(azure_user, attribute_name), attribute_value))
		raise


def check_user_was_deleted(core, user_id):
	# type: (MSGraphApiCore, str) -> None
	print("*** Checking that user was deleted in old adconnection...")
	try:
		deleted_user = UserAzure.get(core, user_id, selection=azure_user_selection)
		if deleted_user.accountEnabled:
			utils.fail("User was not deleted.")
		else:
			print("OK: user was deleted.")
	except MSGraphError:
		print("OK: user was deleted.")