# -*- coding: utf-8 -*-
#
# Univention Office 365 - test_udm_objects
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

import datetime
import os.path
import sys
from copy import copy, deepcopy
import pickle
import pytest
from dateutil.relativedelta import relativedelta
from mock import mock
from six import text_type
from typing import Callable, Tuple

import univention
from test.utils import all_methods_called
from univention.office365 import bool_from_bytes

sys.modules['univention.admin'] = mock.MagicMock()
sys.modules['univention.admin'].uldap.getAdminConnection.return_value = mock.MagicMock(), mock.MagicMock()
sys.modules['univention.debug'] = mock.MagicMock()
sys.modules['univention.config_registry'] = mock.MagicMock()
sys.modules['univention.config_registry.frontend'] = mock.MagicMock()
sys.modules['univention.ldap_cache.cache'] = mock.MagicMock()
sys.modules['univention.ldap_cache.frontend'] = mock.MagicMock()
sys.modules['ldap'] = mock.MagicMock()
sys.modules['ldap.filter'] = mock.MagicMock()

from test import ALIASDOMAIN
from univention.office365.udmwrapper.udmobjects import UDMOfficeUser, UniventionOffice365Data, UDMOfficeObject, Version, UDMOfficeGroup
from univention.office365.udmwrapper import udmobjects
ldap_cred = {}


# def create_udm_object(cls, file):
# 	def _create_udm_object():
# 		test_path = os.path.dirname(os.path.abspath(__file__))
# 		udm_object_reference = pickle.load(open(os.path.join(test_path, "udm_pkl", file), "rb"))
# 		ldap_dict = udm_object_reference["oldattr"]
# 		udm_object = cls(ldap_dict, {}, dn='cn=test,dc=test,dc=test')
# 		udm_object.udm_object_reference = UserDict(udm_object_reference)
# 		udm_object.udm_object_reference.modify = mock.MagicMock()
# 		udm_object.udm_object_reference.oldattr = ldap_dict
# 		return udm_object
# 	return _create_udm_object
#
#
# @pytest.fixture(scope='function')
# def udm_object():
# 	return create_udm_object(UDMOfficeObject, "udm_user_reference.pkl")
#
#
# @pytest.fixture(scope='function')
# def create_udm_user_object():
# 	return create_udm_object(UDMOfficeUser, "udm_user_reference.pkl")
#
#
# @pytest.fixture(scope='function')
# def create_udm_group_object():
# 	return create_udm_object(UDMOfficeGroup, "udm_group_reference.pkl")


@pytest.fixture(scope='function')
def udm_office_raw_user():
	ldap_dict = {
		'dn': [b'cn=test,dc=test,dc=test'],
		'other': [b'test'],
		'username': [b'name'],
		'locked': [b'0'],
		'deactivated': [b'0'],
		'userexpiry': [b'2023-01-01']
	}
	udm_user = UDMOfficeUser(ldap_fields=ldap_dict, ldap_cred=ldap_cred, adconnection_aliases=[ALIASDOMAIN])
	return udm_user


@pytest.fixture(scope='function')
def udm_office_user(udm_office_raw_user):
	udm_office_raw_user.apply_decoding({
		'dn': 'utf-8',
		'other': 'utf-8',
		'username': 'utf-8',
		'locked': 'utf-8',
		'deactivated': 'utf-8',
		'userexpiry': 'utf-8',
	})
	udm_office_raw_user.set_types({
		'dn': text_type,
		'other': text_type,
		'username': text_type,
		'locked': bool_from_bytes,
		'deactivated': bool_from_bytes,
		'userexpiry': text_type,
	})
	return udm_office_raw_user


@pytest.fixture(scope='function')
def udm_office_user_with_fake_udm_user(udm_office_user):
	# Create replacement of the udm_user
	udm_user_dict = {
		"uid": "ontotest",
		"UniventionOffice365Data": "eJwVi0EOgjAQRa9CZm0NhRbBlVs3xitM22kyxs4YBDaEu1vzV+/l/R20H3zSgixwbXZYvzQ/Z5bIH3w/sFC1UFDqbpozR6r9OdFmVuGNZGGVinBqQMOL4nJP/8dkg8VAo+nIoXGDRzP6TGZC13aX1DuyLRzHD5ZvKC0=",
		'groups': ['onegrouptest']
	}
	udm_office_user.udm_object_reference.__getitem__.side_effect = udm_user_dict.__getitem__
	udm_office_user.udm_object_reference.__setitem__.side_effect = udm_user_dict.__setitem__
	udm_office_user.udm_object_reference.update.side_effect = udm_user_dict.update
	return udm_office_user


class TestUDMOfficeObjects:

	def setup(self):
		# type: () -> None
		pass

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, UDMOfficeObject, ["get", "values", "copy", "items", "setdefault", "update", "fromkeys", "keys", "clear", "pop", "popitem"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	def test_set_current_alias(self, udm_object):
		# type: (Callable) -> None
		udm_object = udm_object()  # type: UDMOfficeObject
		with udm_object.set_current_alias("test"):
			assert udm_object.current_connection_alias == "test"

	def test_init(self, udm_object):
		# type: (Callable) -> None
		udm_object = udm_object()
		assert udm_object.dn == 'cn=test,dc=test,dc=test'
		# assert udm_object.other == [b'test']

	def test_init_with_empty_dict(self):
		# type: () -> None
		with pytest.raises(TypeError):
			UDMOfficeObject()

	def test_modified_fields(self, udm_object):
		# type: (Callable) -> None
		# Not encoded as bytes just to test
		udm_object2 = udm_object()
		udm_object = udm_object()
		udm_object2.udm_object_reference["displayName"] = "NewUserName"
		assert udm_object.modified_fields(udm_object2) == ["displayName"]

	def test_deactivate_azure_attributes(self, udm_object):
		# type: (Callable) -> None
		""""""
		udm_user1 = udm_object()
		for alias in udm_user1.aliases():
			udm_user1.deactivate_azure_attributes()
			assert alias not in udm_user1.azure_data

	def test_get_diff_aliases(self, udm_object):
		# type: (Callable) -> None
		""""""
		udm_user1 = udm_object()
		udm_user2 = udm_object()
		assert len(udm_user1.get_diff_aliases(udm_user2)) == 0
		udm_user2.udm_object_reference["UniventionOffice365ADConnectionAlias"] = ["new_alias"]
		assert udm_user1.get_diff_aliases(udm_user2) == ["o365domain"]
		assert udm_user2.get_diff_aliases(udm_user1) == ["new_alias"]

	def test_aliases(self, udm_object):
		# type: (Callable) -> None
		""""""
		udm_user1 = udm_object()
		udm_user1.udm_object_reference["UniventionOffice365ADConnectionAlias"].append("new_alias")
		for alias in udm_user1.aliases():
			assert alias in udm_user1.adconnection_aliases

	def test_create_azure_attributes(self, udm_object):
		# type: (Callable) -> None
		""""""
		udm_user1 = udm_object()
		alias = "new_alias"
		assert alias not in udm_user1.azure_data
		new_data = {"objectId": "test_objectId", "userPrincipalName": "test_userPrincipalName"}
		udm_user1.create_azure_attributes(new_data, alias)
		assert udm_user1.azure_data[alias] == new_data

	def test_modify_azure_attributes(self, udm_object):
		# type: (Callable) -> None
		""""""
		udm_user1 = udm_object()
		udm_user1.udm_object_reference["UniventionOffice365ADConnectionAlias"].append("new_alias")
		for alias in udm_user1.aliases():
			new_data = {"objectId": "test_objectId", "userPrincipalName": "test_userPrincipalName"}
			udm_user1.modify_azure_attributes(new_data)
			assert udm_user1.azure_data[alias] == new_data
		assert "new_alias" in udm_user1.azure_data

	def test_alias_to_modify(self, udm_object):
		# type: (Callable) -> None
		""""""
		udm_user1 = udm_object()
		udm_user2 = udm_object()
		udm_user1.udm_object_reference["UniventionOffice365ADConnectionAlias"].append("new_alias")
		assert list(udm_user1.alias_to_modify(udm_user2)) == ["o365domain"]

	def test_is_version(self, udm_object):
		# type: (Callable) -> None
		""""""
		udm_user1 = udm_object()
		for alias in udm_user1.aliases():
			assert udm_user1.is_version(Version.V3)
		udm_user1.udm_object_reference["UniventionOffice365ObjectID"] = "test_UniventionOffice365ObjectID"
		assert udm_user1.is_version(Version.V1)

	def test_diff_keys(self, udm_object):
		# type: (Callable) -> None
		udm_user1 = udm_object()
		udm_user2 = udm_object()
		assert len(list(udm_user1.diff_keys(udm_user2))) == 0
		udm_user1.udm_object_reference.oldattr["displayName"] = "new_displayName"
		assert udm_user1.diff_keys(udm_user2) == {"displayName"}




class TestUdmOfficeUser:

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, UDMOfficeUser, ["is_version", "items", "popitem", "create_azure_attributes", "alias_to_modify", "keys", "clear", "get_diff_aliases", "setdefault", "modified_fields", "modify_azure_attributes", "deactivate_azure_attributes", "copy", "aliases", "alias_to_deactivate", "update", "get", "pop", "fromkeys", "values", "set_current_alias", "diff_keys"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	def test_from_udm(self, create_udm_user_object):
		# type: (Callable) -> None
		""""""
		udm_user_object = create_udm_user_object()
		UDMOfficeUser.from_udm(udm_user_object.udm_object_reference, {})

	def test_is_expired(self, create_udm_user_object):
		# type: (Callable) -> None
		""""""
		udm_user_object = create_udm_user_object()
		udm_user_object.udm_object_reference["userexpiry"] = (datetime.datetime.today() - relativedelta(days=1)).strftime('%Y-%m-%d')
		assert udm_user_object.is_expired()
		udm_user_object.udm_object_reference["userexpiry"] = (datetime.datetime.today() + relativedelta(days=1)).strftime('%Y-%m-%d')
		assert not udm_user_object.is_expired()

	@pytest.mark.parametrize("params", [
		(False, False, False),
		(False, False, True),
		(False, True, False),
		(False, True, True),
		(True, False, False),
		(True, False, True),
		(True, True, False),
		(True, True, True),
	])
	def test_is_deactivated_locked_or_expired(self, params, create_udm_user_object):
		# type: (Tuple, Callable) -> None
		""""""
		udm_user_object = create_udm_user_object()
		locked, disabled, expired = params
		udm_user_object.udm_object_reference["locked"] = "1" if locked else "0"
		udm_user_object.udm_object_reference["disabled"] = "1" if disabled else "0"
		if expired:
			udm_user_object.udm_object_reference["userexpiry"] = (datetime.datetime.today() - relativedelta(days=1)).strftime('%Y-%m-%d')
		else:
			udm_user_object.udm_object_reference["userexpiry"] = (datetime.datetime.today() + relativedelta(days=1)).strftime('%Y-%m-%d')
		assert udm_user_object.is_deactivated_locked_or_expired() == any(params)

	def test_is_enable(self, create_udm_user_object):
		# type: (Callable) -> None
		udm_user_object = create_udm_user_object()
		udm_user_object.udm_object_reference['UniventionOffice365Enabled'] = "1"
		assert udm_user_object.is_enable()
		udm_user_object.udm_object_reference['UniventionOffice365Enabled'] = "0"
		assert not udm_user_object.is_enable()

	@pytest.mark.parametrize("params", [(True, False, False, False),
										(True, False, False, True),
										(True, False, True, False),
										(True, False, True, True),
										(True, True, False, False),
										(True, True, False, True),
										(True, True, True, False),
										(True, True, True, True),
										(False, False, False, False),
										(False, False, False, True),
										(False, False, True, False),
										(False, False, True, True),
										(False, True, False, False),
										(False, True, False, True),
										(False, True, True, False),
										(False, True, True, True), ])
	def test_should_sync(self, params, create_udm_user_object):
		# type: (Tuple[bool, bool, bool, bool], Callable) -> None
		udm_user_object = create_udm_user_object()
		locked, disabled, expired, enabled = params
		udm_user_object.udm_object_reference["locked"] = "1" if locked else "0"
		udm_user_object.udm_object_reference["disabled"] = "1" if disabled else "0"
		if expired:
			udm_user_object.udm_object_reference["userexpiry"] = (datetime.datetime.today() - relativedelta(days=1)).strftime('%Y-%m-%d')
		else:
			udm_user_object.udm_object_reference["userexpiry"] = (datetime.datetime.today() + relativedelta(days=1)).strftime('%Y-%m-%d')
		udm_user_object.udm_object_reference["UniventionOffice365Enabled"] = "1" if enabled else "0"
		assert udm_user_object.is_deactivated_locked_or_expired() == (locked or disabled or expired)
		assert udm_user_object.is_enable() == enabled
		assert udm_user_object.should_sync() == ((not(locked or disabled or expired)) and enabled)

class TestUdmOfficeGroup:

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, UDMOfficeGroup, ["fromkeys", "keys", "items", "values", "create_azure_attributes", "modified_fields", "copy", "aliases", "popitem", "pop", "setdefault", "update", "deactivate_azure_attributes", "clear", "alias_to_deactivate", "alias_to_modify", "is_version", "get_diff_aliases", "get", "set_current_alias", "get_other_by_displayName", "diff_keys"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	def test_modify_azure_attributes(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group_object = create_udm_group_object()
		for alias in udm_group_object.aliases(["new_alias"]):
			new_data = {"objectId": "test_objectId", "userPrincipalName": "test_userPrincipalName"}
			udm_group_object.modify_azure_attributes(new_data)
			assert udm_group_object.azure_data[alias] == new_data
		assert "new_alias" in udm_group_object.azure_data
		assert "new_alias" in list(udm_group_object.adconnection_aliases)

	def test_delete_azure_data(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group_object = create_udm_group_object()
		for alias in udm_group_object.aliases():
			udm_group_object.delete_azure_data()
			assert alias not in udm_group_object.azure_data
			assert alias not in udm_group_object.adconnection_aliases

	def test_in_azure(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group_object = create_udm_group_object()
		assert not udm_group_object.in_azure()

	def test_is_team(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group_object = create_udm_group_object()
		assert not udm_group_object.is_team()
		udm_group_object.udm_object_reference['UniventionMicrosoft365Team'] = '1'
		assert udm_group_object.is_team()

	def test_get_owners_dn(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group_object = create_udm_group_object()
		owners = ['uid=qye80535ks,cn=users,dc=test-idelgado-com,dc=intranet']
		udm_group_object.udm_object_reference["UniventionMicrosoft365GroupOwners"] = owners
		assert udm_group_object.get_owners_dn() == owners

	def test_get_owners(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group_object = create_udm_group_object()
		owners = ['uid=qye80535ks,cn=users,dc=test-idelgado-com,dc=intranet']
		udm_group_object.udm_object_reference["UniventionMicrosoft365GroupOwners"] = owners
		user_owners = udm_group_object.get_owners()
		assert all([isinstance(x, UDMOfficeUser) for x in user_owners])
		assert all([x.dn in owners for x in user_owners])

	def test_get_nested_group(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group_object = create_udm_group_object()
		data = ['uid=qye80535ks,cn=users,dc=test-idelgado-com,dc=intranet']
		udm_group_object.udm_object_reference["nestedGroup"] = data
		assert udm_group_object.get_nested_group() == data
		
	def test_get_users(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group_object = create_udm_group_object()
		data = ['uid=qye80535ks,cn=users,dc=test-idelgado-com,dc=intranet']
		udm_group_object.udm_object_reference["users"] = data
		assert udm_group_object.get_users() == data
	
	def test_has_azure_users(self, create_udm_group_object,create_udm_user_object):
		# type: (Callable, Callable) -> None
		udm_group_object = create_udm_group_object()
		assert not udm_group_object.has_azure_users()
		udm_user_object = create_udm_user_object()
		bk = udmobjects.UDMOfficeUser
		udmobjects.UDMOfficeUser = mock.MagicMock(return_value=udm_user_object)

		# data_nested = [b'uid=qye80535ks,cn=groups,dc=test-idelgado-com,dc=intranet']
		# udm_group_object.udm_object_reference["nestedGroup"] = data_nested

		data_user = [b'uid=qye80535ks,cn=users,dc=test-idelgado-com,dc=intranet']
		udm_group_object.udm_object_reference["users"] = data_user
		try:
			for alias in udm_group_object.aliases(udm_user_object.adconnection_aliases):
				assert udm_group_object.has_azure_users()
		finally:
			udmobjects.UDMOfficeUser = bk

	@pytest.mark.skip
	def test_get_users_from_ldap(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_group_object = create_udm_group_object()
		assert True == udm_group_object.get_users_from_ldap()
		
	def test_get_groups_member_of_not_in_azure(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_group_object = create_udm_group_object()
		udm_group_object.udm_object_reference["memberOf"] = ["member_of_dn1", "member_of_dn2"]
		bk, udmobjects.UDMOfficeGroup.azure_object_id = udmobjects.UDMOfficeGroup.azure_object_id, None
		k = list(udm_group_object.get_groups_member_of_not_in_azure())
		udmobjects.UDMOfficeGroup.azure_object_id = bk
		assert [x.dn for x in k] == ["member_of_dn1", "member_of_dn2"]
		
	def test_get_members(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_group_object = create_udm_group_object()
		assert udm_group_object.get_members() == [x.decode("utf-8") for x in getattr(udm_group_object, "uniqueMember", [])]
		
	def test_get_nested_groups_with_azure_users(self, create_udm_group_object):
		# type: (Callable) -> None
		udm_group_object = create_udm_group_object()
		udm_group_object.udm_object_reference['nestedGroup'] = ["group_dn1", "group_dn1"]
		udm_group_object.udm_object_reference['users'] = ["user_dn1", "user_dn2"]
		bk, udmobjects.UDMOfficeUser.adconnection_aliases = udmobjects.UDMOfficeUser.adconnection_aliases,["new_alias"]
		with udm_group_object.set_current_alias("new_alias"):
			k = list(udm_group_object.get_nested_groups_with_azure_users())
		udmobjects.UDMOfficeUser.adconnection_aliases = bk
		assert [udm_group_object.dn] == [x.dn for x in k]

	# TODO: refactor initialization with fixtures
	def test_members_changes(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group = create_udm_group_object()
		other_group = create_udm_group_object()
		udm_group.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'})
		other_group.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetoadd,cn=groups,dc=test-idelgado-com,dc=intranet'})

		to_add, to_remove = udm_group.members_changes(other_group)
		assert to_add == {'uid=onetoadd,cn=groups,dc=test-idelgado-com,dc=intranet'}
		assert to_remove == {'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'}

	# TODO: refactor initialization with fixtures
	def test_removed_members(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group = create_udm_group_object()
		other_group = create_udm_group_object()
		udm_group.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'})
		other_group.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetoadd,cn=groups,dc=test-idelgado-com,dc=intranet'})

		to_remove = udm_group.removed_members(other_group)
		assert to_remove == {'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'}

	# TODO: refactor initialization with fixtures
	def test_added_members(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		udm_group = create_udm_group_object()
		other_group = create_udm_group_object()
		udm_group.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'})
		other_group.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetoadd,cn=groups,dc=test-idelgado-com,dc=intranet'})

		to_add = udm_group.added_members(other_group)
		assert to_add == {'uid=onetoadd,cn=groups,dc=test-idelgado-com,dc=intranet'}

	# TODO: refactor initialization with fixtures
	def test_owners_changes(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		first_group = create_udm_group_object()
		other_group = create_udm_group_object()
		first_owners = [mock.MagicMock(name="id %s" % owner_id) for owner_id in range(3)]
		first_group.get_owners = mock.MagicMock(return_value=first_owners)
		other_owners = first_owners[-1:]+[mock.MagicMock(name="id %s" % owner_id) for owner_id in range(3, 4)]
		other_group.get_owners = mock.MagicMock(return_value=other_owners)

		to_add, to_remove = first_group.owners_changes(other_group)
		assert to_add == set(other_owners[-1:])
		assert to_remove == set(first_owners[0:-1])

	# TODO: refactor initialization with fixtures
	def test_removed_owners(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		first_group = create_udm_group_object()
		other_group = create_udm_group_object()
		first_owners = [mock.MagicMock(name="id %s" % owner_id) for owner_id in range(3)]
		first_group.get_owners = mock.MagicMock(return_value=first_owners)
		other_owners = first_owners[-1:]+[mock.MagicMock(name="id %s" % owner_id) for owner_id in range(3, 4)]
		other_group.get_owners = mock.MagicMock(return_value=other_owners)

		to_remove = first_group.removed_owners(other_group)
		assert to_remove == set(first_owners[0:-1])

	# TODO: refactor initialization with fixtures
	def test_added_owners(self, create_udm_group_object):
		# type: (Callable) -> None
		""""""
		first_group = create_udm_group_object()
		other_group = create_udm_group_object()
		first_owners = [mock.MagicMock(name="id %s" % owner_id) for owner_id in range(3)]
		first_group.get_owners = mock.MagicMock(return_value=first_owners)
		other_owners = first_owners[-1:]+[mock.MagicMock(name="id %s" % owner_id) for owner_id in range(3, 4)]
		other_group.get_owners = mock.MagicMock(return_value=other_owners)

		to_add = first_group.added_owners(other_group)
		assert to_add == set(other_owners[-1:])




	