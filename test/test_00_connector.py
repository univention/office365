# -*- coding: utf-8 -*-
#
# Univention Office 365 - test_00_connector
#
# Copyright 2016-2022 Univention GmbH
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

import sys
from unittest.mock import ANY, call

import mock
import pytest
from typing import Callable

import univention.office365.microsoft
from test import DOMAIN_PATH

from test.utils import all_methods_called
univention.office365.microsoft.OFFICE365_API_PATH = DOMAIN_PATH

fake_module = mock.MagicMock()
sys.modules['univention.debug'] = fake_module
setattr(univention, 'debug', fake_module)
sys.modules['lazy_object_proxy'] = mock.MagicMock()
sys.modules['univention.config_registry'] = mock.MagicMock()
pwd_module = mock.MagicMock()
m = mock.Mock()
m.pw_uid = 1000
pwd_module.getpwnam.return_value = m
sys.modules['pwd'] = pwd_module
sys.modules['univention.admin'] = mock.MagicMock()
sys.modules['univention.lib'] = mock.MagicMock()
sys.modules['univention.lib.i18n'] = mock.MagicMock()
sys.modules['univention.admin'].uldap.getAdminConnection.return_value = mock.MagicMock(), mock.MagicMock()
sys.modules['univention.debug'] = mock.MagicMock()
sys.modules['univention.config_registry'] = mock.MagicMock()
sys.modules['univention.config_registry.frontend'] = mock.MagicMock()
sys.modules['univention.ldap_cache.cache'] = mock.MagicMock()
sys.modules['univention.ldap_cache.frontend'] = mock.MagicMock()
sys.modules['univention.lib.i18n'] = mock.MagicMock()
sys.modules['ldap'] = mock.MagicMock()
sys.modules['ldap.filter'] = mock.MagicMock()
sys.modules['os'].chown = mock.MagicMock()

# Mocking grp.getgrnam("nogroup").gr_gid
grp_module = mock.MagicMock()
m = mock.Mock()
m.gr_gid = 1000
grp_module.getgrnam.return_value = m
sys.modules['grp'] = grp_module
sys.modules['univention.lib.i18n'] = mock.MagicMock()
import univention.office365.connector.connector
univention.office365.connector.connector.filter_format = lambda x, y: x % y
from univention.office365.connector.connector import UserConnector, GroupConnector, ConnectorAttributes, UCRHelper, SubscriptionProfile
from univention.office365.microsoft.objects.azureobjects import UserAzure, GroupAzure
from univention.office365.udmwrapper.udmobjects import UniventionOffice365Data
UCRHelper.get_adconnection_filtered_in = mock.MagicMock(return_value=[])
# UCRHelper["office365/subscriptions/service_plan_names"] = None
UCRHelper.get_service_plan_names = mock.MagicMock(return_value=[spn.strip() for spn in "SHAREPOINTWAC, SHAREPOINTWAC_DEVELOPER, OFFICESUBSCRIPTION, OFFICEMOBILE_SUBSCRIPTION, SHAREPOINTWAC_EDU".split(",")])


# "office365/attributes/mapping/l=city",
# "office365/attributes/mapping/displayName=displayName",
# "office365/attributes/mapping/employeeType=jobTitle",
# "office365/attributes/mapping/givenName=givenName",
# "office365/attributes/mapping/mobile=mobilePhone",
# "office365/attributes/mapping/mail=otherMails",
# "office365/attributes/mapping/mailAlternativeAddress=otherMails",
# "office365/attributes/mapping/mailPrimaryAddress=otherMails",
# "office365/attributes/mapping/postalCode=postalCode",
# "office365/attributes/mapping/roomNumber=officeLocation",
# "office365/attributes/mapping/st=usageLocation",
# "office365/attributes/mapping/street=streetAddress",
# "office365/attributes/mapping/sn=surname",
# "office365/attributes/mapping/telephoneNumber=businessPhones",
# "office365/attributes/sync=l,st,displayName,employeeType,givenName,mailPrimaryAddress,mobile,mailAlternativeAddress,mail,postalCode,roomNumber,st,street,sn,telephoneNumber",
# "office365/attributes/anonymize=givenName,street,postalCode",
# "office365/attributes/never=mail,postalCode",
# "office365/attributes/static/roomNumber={}".format(roomNumber),
# "office365/attributes/static/postalCode=12345",
# "office365/attributes/static/l={}".format(city),
# "office365/debug/werror=yes",

@pytest.fixture(scope='function')
def ucr_helper():
	# type: () -> None
	with mock.patch("univention.office365.connector.connector.UCRHelper") as ucr_helper:
		ucr_helper.ucr_split_value.side_effect = [
			["givenName", "street", "postalCode"], ["mail", "postalCode"],
			["l", "st", "displayName", "employeeType", "givenName", "mailPrimaryAddress", "mobile", "mailAlternativeAddress", "mail", "postalCode", "roomNumber", "st", "street", "sn", "telephoneNumber"]
		]
		ucr_helper.ucr_entries_to_dict.side_effect = [
			{
				"l": "city",
				"displayName": "displayName",
				"employeeType": "jobTitle",
				"givenName": "givenName",
				"mobile": "mobilePhone",
				"mail": "otherMails",
				"mailAlternativeAddress": "otherMails",
				"mailPrimaryAddress": "otherMails",
				"postalCode": "postalCode",
				"roomNumber": "officeLocation",
				"st": "usageLocation",
				"street": "streetAddress",
				"sn": "surname",
				"telephoneNumber": "businessPhones",
			},
			{
				"roomNumber": "asdf",
				"postalCode": "asdf",
				"l": "asdf",
			}
		]
		yield ucr_helper


class TestConnectorAttributes:

	def test_completity(self):
		# type: () -> None
		assert all_methods_called(TestConnectorAttributes, ConnectorAttributes, [])

	def test___init__(self):
		# type: () -> None
		a = ConnectorAttributes()
		assert a == {}

	def test_all(self, ucr_helper):
		# type: (mock.MagicMock) -> None
		a = ConnectorAttributes()
		assert a.all == {'displayName', 'employeeType', 'l', 'mailAlternativeAddress', 'mailPrimaryAddress', 'mobile', 'roomNumber', 'sn', 'st', 'telephoneNumber', 'givenName', 'street'}

	def test_update_attributes_from_ucr(self, ucr_helper):
		# type: (mock.MagicMock) -> None
		a = ConnectorAttributes(lazy_load=True)
		a.update_attributes_from_ucr()
		assert a.anonymize == {"givenName", "street", "postalCode"}
		assert a.never == {"mail", "postalCode"}
		assert a.sync == {"l", "st", "displayName", "employeeType", "givenName", "mailPrimaryAddress", "mobile", "mailAlternativeAddress", "mail", "postalCode", "roomNumber", "st", "street", "sn", "telephoneNumber"}
		assert a.static == {"roomNumber": "asdf", "postalCode": "asdf", "l": "asdf"}
		assert a.mapping == {
			"l": "city", "displayName": "displayName", "employeeType": "jobTitle", "givenName": "givenName", "mobile": "mobilePhone", "mail": "otherMails", "mailAlternativeAddress": "otherMails", "mailPrimaryAddress": "otherMails", "postalCode": "postalCode",
			"roomNumber": "officeLocation", "st": "usageLocation", "street": "streetAddress", "sn": "surname", "telephoneNumber": "businessPhones"
		}
		assert a.multiple == {'otherMails': ['mail', 'mailAlternativeAddress', 'mailPrimaryAddress']}

	def test__sanitize(self, ucr_helper):
		# type: (mock.MagicMock) -> None
		a = ConnectorAttributes(lazy_load=True)
		a.update_attributes_from_ucr()
		invalid_attributes = ['justfortest', "univentionOffice365ObjectID", "UniventionOffice365Data"]
		a.sync.update(invalid_attributes)
		a._sanitize()
		assert all([attr not in a.sync for attr in invalid_attributes])

	def test__disjoint_attributes(self, ucr_helper):
		# type: (mock.MagicMock) -> None
		a = ConnectorAttributes(lazy_load=True)
		# Mixing attributes in several sets
		a.update_attributes_from_ucr()
		a.anonymize.update(["mailPrimaryAddress", "displayName"])
		a.never.update(["displayName", "postalCode"])
		a._sanitize()
		a._disjoint_attributes()
		assert all([attr not in a.static for attr in a.never])
		assert all([attr not in a.anonymize for attr in a.never])
		assert all([attr not in a.sync for attr in a.anonymize])


class TestUserConnector:

	def setup_method(self):
		# type: () -> None
		self.uc = UserConnector({'o365domain': "initialized"})
		_attrs = {
			'anonymize': set(),
			'listener': {
				'displayName',
				'employeeType',
				'givenName',
				'krb5KDCFlagskrb5PasswordEnd',
				'krb5ValidEnd',
				'l',
				'mail',
				'mailAlternativeAddress',
				'mailPrimaryAddress',
				'mobile',
				'passwordexpiry',
				'postalCode',
				'roomNumber',
				'sambaAcctFlags',
				'sambaKickoffTime',
				'shadowExpire',
				'shadowLastChange',
				'shadowMax',
				'sn',
				'st',
				'street',
				'telephoneNumber',
				'univentionMicrosoft365Team',
				'univentionOffice365ADConnectionAlias',
				'univentionOffice365Enabled',
				'userPassword',
				'userexpiry'},
			'mapping': {
				'displayName': 'displayName',
				'employeeType': 'jobTitle',
				'givenName': 'givenName',
				'l': 'city',
				'mail': 'otherMails',
				'mailAlternativeAddress': 'otherMails',
				'mailPrimaryAddress': 'otherMails',
				'mobile': 'mobilePhone',
				'postalCode': 'postalCode',
				'roomNumber': 'officeLocation',
				'sn': 'surname',
				'st': 'usageLocation',
				'street': 'streetAddress',
				'telephoneNumber': 'businessPhones'},
			'never': set(),
			'static': set(),
			'sync': {
				'displayName',
				'employeeType',
				'givenName',
				'l',
				'mail',
				'mailAlternativeAddress',
				'mailPrimaryAddress',
				'mobile',
				'postalCode',
				'roomNumber',
				'sn',
				'st',
				'street',
				'telephoneNumber'},
			'multiple': {
				'otherMails': [
					'mail',
					'mailAlternativeAddress',
					'mailPrimaryAddress']}
		}
		for key, value in _attrs.items():
			setattr(self.uc.attrs, key, value)

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, UserConnector, ["anonymize_attr", "_load_filtered_accounts"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	def test_connector_init(self):
		# type: () -> None
		assert self.uc

	def test_get_listener_filter(self):
		# type: () -> None
		""""""
		UCRHelper.get_adconnection_filtered_in = mock.MagicMock(return_value=["o365domain"])
		assert self.uc.get_listener_filter() == "(univentionOffice365ADConnectionAlias=o365domain)"

	def test_has_initialized_connections(self):
		# type: () -> None
		""""""
		assert self.uc.has_initialized_connections() == True

	def test_parse(self, create_udm_user_object):
		# type: (Callable) -> None
		udm_fake_user = create_udm_user_object()
		for _ in udm_fake_user.aliases():
			azure_user = self.uc.parse(udm_fake_user)
			assert azure_user.get_not_none_values_as_dict()['displayName'] == udm_fake_user.displayName
			assert azure_user.get_not_none_values_as_dict()['userPrincipalName'] == udm_fake_user.displayName+'@'+self.uc.cores['o365domain'].account.get_domain()
			assert azure_user.get_not_none_values_as_dict()['onPremisesImmutableId'] == udm_fake_user.entryUUID
			assert azure_user.get_not_none_values_as_dict()['surname'] == udm_fake_user.sn


	# @pytest.mark.skip("Not needed anymore")
	# def test_invalidate_all_tokens(self):
	# 	# type: () -> None
	# 	self.uc._invalidate_all_tokens()



	def test__assign_subscription(self, create_udm_user_object, ucr_helper):
		# type: (Callable, mock.MagicMock) -> None
		udm_fake_user = create_udm_user_object()
		subscription = mock.MagicMock()
		subscription.subscription = "TEAMS_EXPLORATORY"

		SubscriptionProfile.get_profiles_for_groups = mock.MagicMock(return_value=[subscription])
		with mock.patch("univention.office365.connector.connector.SubscriptionAzure") as azure_subscriptions:
			azure_subscriptions.get_enabled = mock.MagicMock(return_value=[mock.MagicMock(skuPartNumber="TEAMS_EXPLORATORY")])
			for _ in udm_fake_user.aliases():
				azure_user = mock.MagicMock(spec=UserAzure, autospec=True)
				azure_user.id = "1234567890"
				self.uc._assign_subscription(udm_fake_user, azure_user)
				azure_user.add_license.assert_called_once()

	def test_prepare_azure_attributes(self):
		# type: () -> None
		azure_user = mock.MagicMock(spec=UserAzure, autospec=True)
		azure_user.id = "1234567890"
		azure_user.userPrincipalName = "name"
		result = self.uc.prepare_azure_attributes(azure_user)
		assert result['objectId'] == azure_user.id
		assert result['userPrincipalName'] == azure_user.userPrincipalName


	def test_new_or_reactivate_user(self, create_udm_user_object):
		# type: (Callable) -> None
		udm_fake_user = create_udm_user_object()
		udm_fake_user.current_connection_alias = "o365domain"
		udm_fake_user.modify_azure_attributes = mock.MagicMock()
		azure_user = mock.MagicMock()
		azure_user.id = "1234567890"
		azure_user.userPrincipalName = "name"
		self.uc.parse = mock.MagicMock(side_effect=[azure_user, mock.MagicMock()])
		self.uc._assign_subscription = mock.MagicMock()
		self.uc.prepare_azure_attributes = mock.MagicMock(return_value={})
		self.uc.group_connector = mock.MagicMock()
		self.uc.new_or_reactivate_user(udm_fake_user)
		self.uc.parse.assert_called_once()
		azure_user.create_or_modify.assert_called_once()
		azure_user.invalidate_all_tokens()
		udm_fake_user.modify_azure_attributes.assert_called_once()

	def test_create(self, create_udm_user_object):
		# type: (Callable) -> None
		udm_fake_user = create_udm_user_object()
		self.uc.new_or_reactivate_user = mock.MagicMock()
		self.uc.create(udm_fake_user)
		# new_or_reactivate_user is called as many times as there are aliases
		self.uc.new_or_reactivate_user.assert_has_calls([mock.call(ANY)]*len(list(udm_fake_user.aliases())))


	def test_delete(self, create_udm_user_object):
		# type: (Callable) -> None
		udm_fake_user = create_udm_user_object()
		udm_fake_user.modify_azure_attributes = mock.MagicMock()
		azure_user = mock.MagicMock()
		azure_user.get_not_none_values_as_dict.return_value = {'displayName': 'test', 'uid': 'testuid', 'objectId': 'testobjectid'}
		self.uc.parse = mock.MagicMock(side_effect=[azure_user, mock.MagicMock()])
		self.uc.delete(udm_fake_user)
		azure_user.deactivate.assert_called_once()


	def test_deactivate(self, create_udm_user_object):
		# type: (Callable) -> None
		udm_fake_user = create_udm_user_object()
		udm_fake_user.modify_azure_attributes = mock.MagicMock()
		azure_user = mock.MagicMock()
		self.uc.parse = mock.MagicMock(side_effect=[azure_user, mock.MagicMock()])
		self.uc.delete(udm_fake_user)
		azure_user.deactivate.assert_called_once()


	def test_modify(self, create_udm_user_object):
		# type: (Callable) -> None
		azure_user_new = mock.MagicMock()
		azure_user_old = mock.MagicMock()
		self.uc.parse = mock.MagicMock(side_effect=[azure_user_old, azure_user_new, mock.MagicMock()])

		# Test users with modified alias for NEW or REACTIVATED account
		# Modify o365domain and add otherconn
		udm_fake_user_old = create_udm_user_object()
		udm_fake_user_new = create_udm_user_object()
		udm_fake_user_new.modify_azure_attributes = mock.MagicMock()
		self.uc.new_or_reactivate_user = mock.MagicMock()
		udm_fake_user_old.udm_object_reference["UniventionOffice365ADConnectionAlias"] = ["o365domain"]
		udm_fake_user_new.udm_object_reference["UniventionOffice365ADConnectionAlias"] = ["o365domain", "otherconn"]
		self.uc.modify(udm_fake_user_old, udm_fake_user_new)
		self.uc.new_or_reactivate_user.assert_called_once()
		azure_user_old.update.assert_called_with(azure_user_new)
		udm_fake_user_new.modify_azure_attributes.assert_called_once()
		assert self.uc.parse.call_count == 2

		# Test removed connections
		# Remove otherconn1	from aliases and modify o365domain and otherconn2
		udm_fake_user_old = create_udm_user_object()
		udm_fake_user_new = create_udm_user_object()
		udm_fake_user_new.modify_azure_attributes = mock.MagicMock()
		udm_fake_user_old.udm_object_reference["UniventionOffice365ADConnectionAlias"] = ["o365domain", "otherconn1", "otherconn2"]
		udm_fake_user_new.udm_object_reference["UniventionOffice365ADConnectionAlias"] = ["o365domain", "otherconn2"]
		self.uc.parse = mock.MagicMock(side_effect=[azure_user_old, azure_user_old, azure_user_new,  azure_user_old, azure_user_new, mock.MagicMock()])

		self.uc.modify(udm_fake_user_old, udm_fake_user_new)
		assert self.uc.parse.call_count == 5
		azure_user_old.deactivate.assert_called_once()
		# One call for remove, two calls for modifications
		assert udm_fake_user_new.modify_azure_attributes.call_count == 3

		# Test modified connections
		# Modify attributes in the 3 connections
		udm_fake_user_old = create_udm_user_object()
		udm_fake_user_new = create_udm_user_object()
		udm_fake_user_new.udm_object_reference["UniventionOffice365ADConnectionAlias"] = ["o365domain", "otherconn1", "otherconn2"]
		udm_fake_user_old.udm_object_reference["UniventionOffice365ADConnectionAlias"] = ["o365domain", "otherconn1", "otherconn2"]
		udm_fake_user_new.modify_azure_attributes = mock.MagicMock()
		self.uc.parse = mock.MagicMock(side_effect=[azure_user_old, azure_user_new,  azure_user_old, azure_user_new, azure_user_old, azure_user_new, ])
		udm_fake_user_new.street = "other_street"
		self.uc.modify(udm_fake_user_old, udm_fake_user_new)
		# One call for each connection
		assert udm_fake_user_new.modify_azure_attributes.call_count == 3

	def test_check_permissions(self):
		# type: () -> None
		for core in self.uc.cores.values():
			core.get_permissions = mock.MagicMock(retunr_value={"@odata.context": "https://graph.microsoft.com/v1.0/$metadata#servicePrincipals('d521afe4-7a36-40de-9fcd-a63239268712')/appRoleAssignments(appRoleId)","value": [{"appRoleId": "78c8a3c8-a07e-4b9e-af1b-b5ccab50a175"},{"appRoleId": "741f803b-c850-494e-b5df-cde7c675a1ca"},{"appRoleId": "19dbc75e-c2e2-444c-a770-ec69d8559fc7"},{"appRoleId": "62a82d76-70ea-41e2-9197-370581804d09"},{"appRoleId": "0121dc95-1b9f-4aed-8bac-58c5ac466691"}]})
		self.uc.check_permissions()
		for core in self.uc.cores.values():
			core.get_permissions.assert_called_once()

class TestGroupConnector:

	def setup_method(self):
		# type: () -> None
		self.gc = GroupConnector({'o365domain': "initialized"})
		self.gc.async_task = False

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, GroupConnector, ["check_permissions"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	def test_parse(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group = create_udm_group_object()
		udm_fake_group.current_connection_alias = "o365domain"
		udm_fake_group.create_azure_attributes = mock.MagicMock()
		azure_group = self.gc.parse(udm_fake_group)
		assert azure_group.displayName == udm_fake_group.cn
		assert azure_group.description == udm_fake_group.description
		assert azure_group.id == udm_fake_group.azure_object_id

	def test_add_ldap_members_to_azure_group(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group = create_udm_group_object()
		udm_fake_group.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group.current_connection_alias = "o365domain"
		udm_fake_group.get_users_from_ldap = mock.MagicMock(return_value=["user1", "user2", "group1"])
		groups_member_of_not_in_azure = [mock.MagicMock()]*2
		udm_fake_group.get_groups_member_of_not_in_azure = mock.MagicMock(side_effect=[groups_member_of_not_in_azure])
		self.gc.current_connection_alias = "o365domain"
		self.gc._create_group = mock.MagicMock()
		nested_group = mock.MagicMock()
		nested_group.azure_object_id="nested_id"
		udm_fake_group.get_nested_groups_with_azure_users = mock.MagicMock(return_value=[nested_group])
		azure_object = mock.MagicMock()
		azure_object.id = "azure_object_id"
		self.gc.add_ldap_members_to_azure_group(udm_fake_group, azure_object)
		# Check add_member is called with the names of the members
		azure_object.add_members.assert_called_once_with(["user1", "user2", "group1"])
		# Check the group creation of the members of udm_fake_group not in azure
		self.gc._create_group.assert_has_calls([call(x) for x in groups_member_of_not_in_azure])


	def test__create_group(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group = create_udm_group_object()
		udm_fake_group.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group.current_connection_alias = "o365domain"

		azure_group = mock.MagicMock()
		azure_group.id = "azure_object_id"
		self.gc.parse = mock.MagicMock(return_value=azure_group)
		self.gc.add_ldap_members_to_azure_group = mock.MagicMock()

		result = self.gc._create_group(udm_fake_group)
		assert result == azure_group
		azure_group.create_or_modify.assert_called_once()
		self.gc.parse.assert_called_once_with(udm_fake_group)
		self.gc.add_ldap_members_to_azure_group.assert_called_once_with(udm_fake_group, azure_group)

	def test_convert_group_to_team(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_fake_group = create_udm_group_object()
		udm_fake_group.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group.is_team = mock.MagicMock(return_value=True)
		udm_fake_group.current_connection_alias = "o365domain"
		owners = [mock.MagicMock()]*2
		udm_fake_group.get_owners = mock.MagicMock(return_value=owners)
		azure_group = mock.MagicMock()
		azure_group.id = "azure_object_id"
		azure_group.resourceProvisioningOptions = []
		with mock.patch("univention.office365.connector.connector.TeamAzure") as mock_team,\
			mock.patch("univention.office365.connector.connector.GroupAzure") as mock_group:
			mock_team.create_from_group = mock.MagicMock()
			mock_group.get = mock.MagicMock(return_value=azure_group)

			self.gc.convert_group_to_team(udm_fake_group, azure_group)
			azure_group.add_owner.assert_has_calls([call(ANY, async_task=False) for x in owners])
			mock_team.create_from_group.assert_called_once_with(ANY, azure_group.id)

	def test_create(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group = create_udm_group_object()
		udm_fake_group.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group.is_team = mock.MagicMock(return_value=True)
		azure_group = mock.MagicMock()
		azure_group.id = "azure_object_id"
		self.gc._create_group = mock.MagicMock(return_value=azure_group)
		self.gc.convert_group_to_team = mock.MagicMock()
		self.gc.create(udm_fake_group)
		self.gc._create_group.assert_called_once_with(udm_fake_group)
		self.gc.convert_group_to_team.assert_called_once_with(udm_fake_group, azure_group)

	def test_delete(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group = create_udm_group_object()
		udm_fake_group.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group.is_team = mock.MagicMock(return_value=True)
		azure_group = mock.MagicMock()
		azure_group.id = "azure_object_id"
		self.gc.parse = mock.MagicMock(return_value=azure_group)
		udm_fake_group.udm_object_reference["UniventionOffice365Data"] = UniventionOffice365Data({'o365domain': {'objectId': 'the_object_id'}}).to_ldap_str()
		with mock.patch("univention.office365.connector.connector.TeamAzure") as mock_team:
			self.gc.delete(udm_fake_group)
			mock_team.return_value.deactivate.assert_called_once()
			azure_group.remove_direct_members.assert_called_once()
			azure_group.deactivate.assert_called_once()


	def test_check_and_modify_teams(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group_old = create_udm_group_object()
		udm_fake_group_old.current_connection_alias = "o365domain"

		udm_fake_group_new = create_udm_group_object()

		azure_group = mock.MagicMock()
		azure_group.id = "azure_object_id"
		self.gc.parse = mock.MagicMock(return_value=azure_group)
		self.gc.convert_group_to_team = mock.MagicMock()

		# Check for new team
		udm_fake_group_old.is_team = mock.MagicMock(return_value=False)
		udm_fake_group_new.is_team = mock.MagicMock(return_value=True)

		self.gc.check_and_modify_teams(udm_fake_group_old, udm_fake_group_new, azure_group)
		self.gc.convert_group_to_team.assert_called_once_with(udm_fake_group_new, azure_group)

		# Check deactivate/remove team
		udm_fake_group_old.is_team = mock.MagicMock(return_value=True)
		udm_fake_group_new.is_team = mock.MagicMock(return_value=False)
		with mock.patch("univention.office365.connector.connector.TeamAzure") as mock_team:
			self.gc.check_and_modify_teams(udm_fake_group_old, udm_fake_group_new, azure_group)
			mock_team.get.return_value.deactivate.assert_called_once()

	def test_check_and_modify_owners(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group_old = create_udm_group_object()
		udm_fake_group_old.current_connection_alias = "o365domain"

		udm_fake_group_new = create_udm_group_object()

		azure_group = mock.MagicMock()
		azure_group.id = "azure_object_id"
		self.gc.parse = mock.MagicMock(return_value=azure_group)

		self.gc.convert_group_to_team = mock.MagicMock()

		# Check owners to add
		old_owners = [mock.MagicMock(dn=dn) for dn in ['uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet']]
		new_owners = old_owners + [mock.MagicMock(dn=dn) for dn in ['uid=newowner,cn=users,dc=test-idelgado-com,dc=intranet']]
		udm_fake_group_old.get_owners = mock.MagicMock(return_value=old_owners)
		udm_fake_group_new.get_owners = mock.MagicMock(return_value=new_owners)
		# udm_fake_group_old.owners_changes = mock.MagicMock()

		self.gc.check_and_modify_owners(udm_fake_group_old, udm_fake_group_new, azure_group)
		azure_group.add_owner.assert_called_once()

		# Check owners to remove
		old_owners = [mock.MagicMock(dn=dn, name=dn) for dn in ['uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=ownertoremove,cn=users,dc=test-idelgado-com,dc=intranet']]
		new_owners = old_owners[0:1]
		udm_fake_group_old.get_owners = mock.MagicMock(return_value=old_owners)
		udm_fake_group_new.get_owners = mock.MagicMock(return_value=new_owners)

		self.gc.check_and_modify_owners(udm_fake_group_old, udm_fake_group_new, azure_group)
		azure_group.add_owner.assert_called_once()

	def test_delete_empty_group(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group_new = create_udm_group_object()
		udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group_new.is_team = mock.MagicMock(return_value=True)
		udm_fake_group_new.current_connection_alias = "o365domain"

		azure_group = mock.MagicMock()
		azure_group.id = "azure_object_id"
		azure_group.list_members = mock.MagicMock()
		azure_group.member_of = mock.MagicMock()

		# Check delete of group with active members
		assert self.gc.delete_empty_group(azure_group, udm_fake_group_new) is False

		# Check delete of group without active members
		azure_group.list_members = mock.MagicMock(return_value=[])
		azure_group.remove_direct_members = mock.MagicMock()
		azure_group.deactivate = mock.MagicMock()

		udm_fake_group_new.deactivate_azure_attributes = mock.MagicMock()

		self.gc.delete_empty_group(azure_group, udm_fake_group_new)
		azure_group.remove_direct_members.assert_called_once()
		azure_group.deactivate.assert_called_once()
		udm_fake_group_new.deactivate_azure_attributes.assert_called_once()

	def test_check_and_modify_members(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group_old = create_udm_group_object()
		udm_fake_group_old.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group_old.is_team = mock.MagicMock(return_value=True)

		udm_fake_group_old.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'})

		udm_fake_group_new = create_udm_group_object()
		udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group_new.is_team = mock.MagicMock(return_value=True)

		udm_fake_group_new.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetobeadded,cn=groups,dc=test-idelgado-com,dc=intranet'})

		azure_group = mock.MagicMock()
		azure_group.id = "azure_object_id"
		azure_group.add_members = mock.MagicMock()
		azure_group.remove_member = mock.MagicMock()
		self.gc.parse = mock.MagicMock(return_value=azure_group)

		# Check for member not in nested groups or users RuntimeError
		with pytest.raises(RuntimeError):
			self.gc.check_and_modify_members(udm_fake_group_old, udm_fake_group_new, azure_group)

		# Check member "to add" is user:
		udm_fake_group_old.get_users = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
		udm_fake_group_old.get_nested_group = mock.MagicMock(return_value={'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'})

		udm_fake_group_new.get_users = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
		udm_fake_group_new.get_nested_group = mock.MagicMock(return_value={'uid=onetobeadded,cn=groups,dc=test-idelgado-com,dc=intranet'})
		udm_fake_group_new.current_connection_alias = "azuretestdomain"

		udm_group = create_udm_group_object()
		udm_group.get_nested_groups_with_azure_users = mock.MagicMock(return_value=[udm_group])
		udm_group.get_nested_group = mock.MagicMock(return_value={'cn=test,dc=test,dc=test'})
		with mock.patch("univention.office365.connector.connector.UDMOfficeGroup", mock.MagicMock(return_value=udm_group)),\
				mock.patch("univention.office365.connector.connector.GroupAzure.get_by_name", mock.MagicMock(return_value=None)),\
				mock.patch("univention.office365.connector.connector.TeamAzure") as mock_team:
			self.gc.cores["azuretestdomain"] = self.gc.cores["o365domain"]
			self.gc.check_and_modify_members(udm_fake_group_old, udm_fake_group_new, azure_group)
			self.gc.cores.pop("azuretestdomain")
			azure_group.add_members.assert_called_once()
			azure_group.remove_member.assert_called_once()

		# Check for empty group (removed_members_dn and not added_members_dn)
		self.gc.delete_empty_group = mock.MagicMock()
		azure_group.remove_member = mock.MagicMock()
		udm_fake_group_old.get_users = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
		udm_fake_group_old.get_nested_group = mock.MagicMock(return_value={'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'})

		udm_fake_group_new.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
		udm_fake_group_new.get_users = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
		udm_fake_group_new.current_connection_alias = "azuretestdomain"
		with mock.patch("univention.office365.connector.connector.UDMOfficeGroup",
						mock.MagicMock(return_value=create_udm_group_object())), mock.patch("univention.office365.connector.connector.GroupAzure.get_by_name", mock.MagicMock(return_value=None)):
			self.gc.check_and_modify_members(udm_fake_group_old, udm_fake_group_new, azure_group)
			azure_group.remove_member.assert_called_once()
			self.gc.delete_empty_group.assert_called_once_with(azure_group, udm_fake_group_new)


	def test_check_and_modify_attributes(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group_new = create_udm_group_object()
		udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group_new.is_team = mock.MagicMock(return_value=True)

		azure_group = mock.MagicMock()
		azure_group.id = "azure_object_id"

		new_azure_group = mock.MagicMock()
		new_azure_group.id = "new_azure_object_id"
		self.gc.parse = mock.MagicMock(return_value=new_azure_group)

		self.gc.check_and_modify_attributes(udm_fake_group_new, azure_group)
		azure_group.update.assert_called_once_with(new_azure_group)

	def test_modify(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_group_old = create_udm_group_object()
		udm_fake_group_old.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group_old.is_team = mock.MagicMock(return_value=True)

		udm_fake_group_new = create_udm_group_object()
		udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
		udm_fake_group_new.is_team = mock.MagicMock(return_value=True)
		udm_fake_group_new.modify_azure_attributes = mock.MagicMock()

		azure_group = mock.MagicMock(name="azure_group")
		azure_group.id = "azure_object_id"
		new_azure_group = mock.MagicMock(name="new_azure_group")
		new_azure_group.id = "azure_object_id"
		self.gc.parse = mock.MagicMock(side_effect=[new_azure_group])

		created_group = mock.MagicMock(name="new_create_azure_group")
		created_group.id = "created_group_object_id"
		self.gc._create_group = mock.MagicMock(return_value=created_group)

		# Check no modifications
		self.gc.modify(udm_fake_group_old, udm_fake_group_new)
		udm_fake_group_new.modify_azure_attributes.assert_not_called()


		# Check modifications TODO:
		self.gc._create_group = mock.MagicMock(return_value=created_group)
		self.gc.parse = mock.MagicMock(side_effect=[azure_group, new_azure_group])
		udm_fake_group_new.udm_object_reference.oldattr["description"] = b"the new description"
		self.gc.check_and_modify_teams = mock.MagicMock()
		self.gc.check_and_modify_owners = mock.MagicMock()
		self.gc.check_and_modify_members = mock.MagicMock()
		self.gc.check_and_modify_attributes = mock.MagicMock()

		self.gc.modify(udm_fake_group_old, udm_fake_group_new)

		self.gc._create_group.assert_called_once()
		self.gc.parse.assert_called_with(udm_fake_group_new)
		created_group.update.assert_called_with(azure_group)
		self.gc.check_and_modify_teams.assert_called_once_with(udm_fake_group_old, udm_fake_group_new, created_group)
		self.gc.check_and_modify_owners.assert_called_once_with(udm_fake_group_old, udm_fake_group_new, created_group)
		self.gc.check_and_modify_members.assert_called_once_with(udm_fake_group_old, udm_fake_group_new, created_group)
		self.gc.check_and_modify_attributes.assert_called_once_with(udm_fake_group_new, created_group)

	def test_add_member(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_user = mock.MagicMock()
		udm_fake_group = create_udm_group_object()
		udm_fake_group.current_connection_alias = "o365domain"
		azure_group = mock.MagicMock()
		self.gc.parse = mock.MagicMock(return_value=azure_group)

		self.gc.add_member(udm_fake_group, udm_fake_user)
		self.gc.parse.assert_called_once_with(udm_fake_group)
		azure_group.add_member.assert_called_once_with(udm_fake_user.azure_object_id)

	def test_remove_member(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_fake_user = mock.MagicMock()
		udm_fake_group = create_udm_group_object()
		udm_fake_group.current_connection_alias = "o365domain"
		azure_group = mock.MagicMock()
		self.gc.parse = mock.MagicMock(return_value=azure_group)

		self.gc.remove_member(udm_fake_group, udm_fake_user)
		self.gc.parse.assert_called_once_with(udm_fake_group)
		azure_group.remove_member.assert_called_once_with(udm_fake_user.azure_object_id)

	def test_get_listener_filter(self):
		# type: () -> None
		with mock.patch("univention.office365.connector.connector.UCRHelper") as ucr_helper:
			ucr_helper.get_adconnection_filtered_in = mock.MagicMock(return_value=["o365domain"])
			assert self.gc.get_listener_filter() == '(univentionOffice365ADConnectionAlias=o365domain)'

	def test_has_initialized_connections(self):
		# type: () -> None
		assert self.gc.has_initialized_connections()

	def test_prepare_azure_attributes(self):
		# type: () -> None
		azure_user = mock.MagicMock(id="test_id", userPrincipalName="test_display_name")
		assert self.gc.prepare_azure_attributes(azure_user) == {"objectId": "test_id"}


