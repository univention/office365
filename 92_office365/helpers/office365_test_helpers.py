"""
Common functions used by tests.
"""
# Copyright 2016-2018 Univention GmbH
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

import random
import pprint
from operator import itemgetter
import base64
import logging

import univention.admin.syntax as udm_syntax
import univention.testing.strings as uts

from univention.office365.azure_handler import ResourceNotFoundError
from univention.office365.logging2udebug import get_logger, LevelDependentFormatter


udm2azure = dict(
	firstname=lambda x: itemgetter("givenName")(x),
	lastname=lambda x: itemgetter("surname")(x),
	set=dict(
		city=lambda x: itemgetter("city")(x),
		country=lambda x: itemgetter("usageLocation")(x),
		displayName=lambda x: itemgetter("displayName")(x),
		employeeType=lambda x: itemgetter("jobTitle")(x),
		mailPrimaryAddress=lambda x: itemgetter("otherMails")(x),
		postcode=lambda x: itemgetter("postalCode")(x),
		roomNumber=lambda x: itemgetter("physicalDeliveryOfficeName")(x),
		street=lambda x: itemgetter("streetAddress")(x)
	),
	append=dict(
		mailAlternativeAddress=lambda x: itemgetter("otherMails")(x),
		mobileTelephoneNumber=lambda x: itemgetter("mobile")(x),
		phone=lambda x: itemgetter("telephoneNumber")(x)
	)
)
udm2azure["append"]["e-mail"] = lambda x: itemgetter("otherMails")(x)

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
		mobile="mobile",
		postalCode="postalCode",
		roomNumber="physicalDeliveryOfficeName",
		sn="surname",
		st="usageLocation",
		street="streetAddress",
		telephoneNumber="telephoneNumber",
	),
	never=[],
	static=[],
	sync=[
		"city", "displayName", "e-mail", "employeeType", "givenName", "jpegPhoto", "mailAlternativeAddress",
		"mailPrimaryAddress", "mobile", "postalCode", "roomNumber", "sn", "st", "st", "street", "telephoneNumber"
	]
)


class AzureDirectoryTestObjects(object):
	def __init__(self, otype, a_handler, obj_ids=None):
		"""
		Context manager that deletes the azure objects when leaving it.
		:param otype: str: type of object to delete ("user", "group")
		:param a_handler: AzureHandler object
		:param obj_ids: list of object IDs to delete from azure when leaving
		the context manager
		"""
		assert otype in ["user", "group"]
		self._otype = otype
		assert isinstance(obj_ids, list)
		self._obj_ids = obj_ids
		self._a_handler = a_handler

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		if not self._a_handler:
			return
		for obj_id in self._obj_ids:
			print(">>> Deleting test-{} '{}'...".format(self._otype, obj_id))
			try:
				obj = getattr(self._a_handler, "delete_{}".format(self._otype))(obj_id)
			except ResourceNotFoundError:
				print(">>> OK: Doesn't exist (anymore): {} '{}'.".format(self._otype, obj_id))
				continue

			if self._otype == "user" and obj and obj["accountEnabled"]:
				print(">>> Fail: could not delete test-{} '{}': {}".format(self._otype, obj_id, obj))
			else:
				print(">>> OK: deactivated test-{} '{}'.".format(self._otype, obj_id))


class AzureDirectoryTestUsers(AzureDirectoryTestObjects):
	def __init__(self, a_handler, user_ids=None):
		"""
		Context manager that deletes the azure users when leaving it.
		:param a_handler: AzureHandler object
		:param user_ids: list of user IDs to delete from azure
		when leaving the context manager
		"""
		super(AzureDirectoryTestUsers, self).__init__("user", a_handler, user_ids)


class AzureDirectoryTestGroups(AzureDirectoryTestObjects):
	def __init__(self, a_handler, group_ids=None):
		"""
		Context manager that deletes the azure groups when leaving it.
		:param a_handler: AzureHandler object
		:param group_ids: list of group IDs to delete from azure
		when leaving the context manager
		"""
		super(AzureDirectoryTestGroups, self).__init__("group", a_handler, group_ids)


def print_users(users, complete=False, short=False):
	if not users:
		print("None.")
		return
	if isinstance(users, list):
		users = users
	elif isinstance(users, dict) and "odata.metadata" in users and users["odata.metadata"].endswith("@Element"):
		users = [users]
	else:
		users = users["value"]
	for user in users:
		print(u"objectType: {0} objectId: {1} accountEnabled: {2} displayName: '{3}'".format(
			user["objectType"],
			user["objectId"],
			user["accountEnabled"],
			user["displayName"])
		)
		if short:
			pass
		elif complete:
			pprint.pprint(user)
			print("")
		else:
			for attr in ["accountEnabled", "displayName", "mail", "odata.type", "otherMails", "userPrincipalName"]:
				if attr in user:
					print(u"      {0}: {1}".format(attr, user[attr]))
				else:
					print("      no attr {0}".format(attr))
			print("      assignedPlans:")
			for plan in user["assignedPlans"]:
				print(u"            service: {0} \t capabilityStatus: {1}".format(
					plan["service"],
					plan["capabilityStatus"]
				))
			if not user["assignedPlans"]:
				print("            None")
			print("      provisionedPlans:")
			for plan in user["provisionedPlans"]:
				print(u"            service: {0} \t capabilityStatus: {0} \t provisioningStatus: {0}".format(
					plan["service"],
					plan["capabilityStatus"],
					plan["provisioningStatus"]
				))
			if not user["provisionedPlans"]:
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


def azure_user_args(azure_handler, minimal=True):
	local_part_email = uts.random_username()
	domain = azure_handler.get_verified_domain_from_disk()
	res = dict(
		accountEnabled=True,
		displayName=uts.random_string(),
		immutableId=base64.encodestring(uts.random_string()).rstrip(),
		mailNickname=local_part_email,
		passwordProfile=dict(
			password=azure_handler.create_random_pw(),
			forceChangePasswordNextLogin=False
		),
		userPrincipalName="{0}@{1}".format(local_part_email, domain)
	)
	if not minimal:
		res.update(dict(
			city=uts.random_string(),
			country=random.choice(map(itemgetter(0), udm_syntax.Country.choices)),
			givenName=uts.random_string(),
			jobTitle=uts.random_string(),
			otherMails=[
				"{}@{}".format(uts.random_string(), uts.random_string()),
				"{}@{}".format(uts.random_string(), uts.random_string())
			],
			mobile=uts.random_string(),
			postalCode=uts.random_string(),
			physicalDeliveryOfficeName=uts.random_string(),
			usageLocation=random.choice(map(itemgetter(0), udm_syntax.Country.choices)),
			streetAddress=uts.random_string(),
			surname=uts.random_string(),
			telephoneNumber=uts.random_string(),
		))
	return res


def udm_user_args(ucr, minimal=True):
	res = dict(
		firstname=uts.random_string(),
		lastname=uts.random_string(),
		set=dict(
			displayName=uts.random_string(),
			password=uts.random_string(),
			mailHomeServer="{}.{}".format(ucr["hostname"], ucr["domainname"]),
			mailPrimaryAddress="{}@{}".format(uts.random_username(), ucr["domainname"]),
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
			country=random.choice(map(itemgetter(0), udm_syntax.Country.choices)),
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


def check_udm2azure_user(udm_args, azure_user, complete=True):
	res = list()
	fail = False
	for k, v in [("firstname", udm2azure["firstname"]), ("lastname", udm2azure["lastname"])]:
		try:
			udm_value = udm_args[k]
		except KeyError:
			if complete:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			continue
		azure_value = v(azure_user)
		if udm_value != azure_value:
			fail = True
			res.append((k, udm_value, azure_value))

	for k, v in udm2azure["set"].items():
		try:
			udm_value = udm_args["set"][k]
		except KeyError:
			if complete:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			continue
		try:
			azure_value = v(azure_user)
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

	for k, v in udm2azure["append"].items():
		try:
			udm_values = udm_args["append"][k]
		except KeyError:
			if complete:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			continue
		azure_values = v(azure_user)
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
