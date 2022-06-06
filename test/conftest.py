from six.moves import UserDict

import os
import pickle
import sys

import pytest
from mock import mock
from mock.mock import MagicMock
from typing import Callable, Any, Dict, Union, List

ldap_cred = {}

@pytest.fixture(scope='session')
def mock_univention_libs():
	# type: () -> None
	univention_libs = ['listener', 'univention.lib', 'univention.office365.azure_auth', 'univention.office365.listener',
					   'univention.office365.udm_helper', 'univention.office365.logging2udebug',
					   'univention.office365.api_helper', 'univention.config_registry', 'univention.debug', 'univention.admin']
	old = {k: sys.modules[k] for k in univention_libs if k in sys.modules}
	for k in univention_libs:
		sys.modules[k] = MagicMock()
	yield old
	for k in univention_libs:
		if k in old:
			sys.modules[k] = old[k]


def create_udm_object(cls, file, mapping):
	# type: (Callable, str, Dict[str, Any]) -> Callable
	unmapName = {v: k for k, v in mapping.items()}
	def _create_udm_object():
		# type: () -> Any
		test_path = os.path.dirname(os.path.abspath(__file__))
		udm_object_reference = pickle.load(open(os.path.join(test_path, "udm_pkl", file), "rb"))
		ldap_dict = udm_object_reference["oldattr"]
		udm_object = cls(ldap_dict, {}, dn='cn=test,dc=test,dc=test')
		udm_object.udm_object_reference = UserDict(udm_object_reference)
		udm_object.udm_object_reference.modify = mock.MagicMock()
		udm_object.udm_object_reference.oldattr = ldap_dict
		udm_object.udm_object_reference.mapping = mock.MagicMock()
		udm_object.udm_object_reference.mapping.unmapName = lambda x: unmapName[x] if x in unmapName else ""
		from univention.office365.ucr_helper import UCRHelper
		UCRHelper.get_usage_location = mock.MagicMock(return_value="DE")
		udm_object.udm_object_reference["groups"] = ["cn=test,dc=test,dc=test"]
		return udm_object
	return _create_udm_object


# @pytest.fixture(scope='session', autouse=True)
# def get_udm_object():
# 	from univention.office365.udm_helper import UDMHelper
# 	sys.modules["univention.office365.udm_helper.UDMHelper"] = MagicMock(spec=UDMHelper, autospec=True)

@pytest.fixture(scope='function')
def udm_object(mock_univention_libs):
	# type: (mock.MagicMock) -> Callable
	from univention.office365.udmwrapper.udmobjects import UDMOfficeObject
	mapping = {
		'username': 'uid',
		'uidNumber': 'uidNumber',
		'gidNumber': 'gidNumber',
		'title': 'title',
		'initials': 'initials',
		'description': 'description',
		'organisation': 'o',
		'mailPrimaryAddress': 'mailPrimaryAddress',
		'mailAlternativeAddress': 'mailAlternativeAddress',
		'mailHomeServer': 'univentionMailHomeServer',
		'mailForwardAddress': 'mailForwardAddress',
		'preferredLanguage': 'preferredLanguage',
		'street': 'street',
		'e-mail': 'mail',
		'postcode': 'postalCode',
		'postOfficeBox': 'postOfficeBox',
		'city': 'l',
		'country': 'st',
		'phone': 'telephoneNumber',
		'roomNumber': 'roomNumber',
		'employeeNumber': 'employeeNumber',
		'employeeType': 'employeeType',
		'secretary': 'secretary',
		'departmentNumber': 'departmentNumber',
		'mobileTelephoneNumber': 'mobile',
		'pagerTelephoneNumber': 'pager',
		'homeTelephoneNumber': 'homePhone',
		'homePostalAddress': 'homePostalAddress',
		'officeLocation': 'physicalDeliveryOfficeName',
		'preferredDeliveryMethod': 'preferredDeliveryMethod',
		'unixhome': 'homeDirectory',
		'shell': 'loginShell',
		'sambahome': 'sambaHomePath',
		'sambaUserWorkstations': 'sambaUserWorkstations',
		'sambaLogonHours': 'sambaLogonHours',
		'sambaPrivileges': 'univentionSambaPrivilegeList',
		'scriptpath': 'sambaLogonScript',
		'profilepath': 'sambaProfilePath',
		'homedrive': 'sambaHomeDrive',
		'gecos': 'gecos',
		'displayName': 'displayName',
		'birthday': 'univentionBirthday',
		'lastname': 'sn',
		'firstname': 'givenName',
		'userCertificate': 'userCertificate;binary',
		'jpegPhoto': 'jpegPhoto',
		'umcProperty': 'univentionUMCProperty',
		'lockedTime': 'sambaBadPasswordTime',
		'accountActivationDate': 'krb5ValidStart',
		'password': 'userPassword'
	}
	return create_udm_object(UDMOfficeObject, "udm_user_reference.pkl", mapping)


@pytest.fixture(scope='function')
def create_udm_user_object(mock_univention_libs):
	# type: (mock.MagicMock) -> Callable
	from univention.office365.udmwrapper.udmobjects import UDMOfficeUser
	user_mapping = {
		'username': 'uid',
		'uidNumber': 'uidNumber',
		'gidNumber': 'gidNumber',
		'title': 'title',
		'initials': 'initials',
		'description': 'description',
		'organisation': 'o',
		'mailPrimaryAddress': 'mailPrimaryAddress',
		'mailAlternativeAddress': 'mailAlternativeAddress',
		'mailHomeServer': 'univentionMailHomeServer',
		'mailForwardAddress': 'mailForwardAddress',
		'preferredLanguage': 'preferredLanguage',
		'street': 'street',
		'e-mail': 'mail',
		'postcode': 'postalCode',
		'postOfficeBox': 'postOfficeBox',
		'city': 'l',
		'country': 'st',
		'phone': 'telephoneNumber',
		'roomNumber': 'roomNumber',
		'employeeNumber': 'employeeNumber',
		'employeeType': 'employeeType',
		'secretary': 'secretary',
		'departmentNumber': 'departmentNumber',
		'mobileTelephoneNumber': 'mobile',
		'pagerTelephoneNumber': 'pager',
		'homeTelephoneNumber': 'homePhone',
		'homePostalAddress': 'homePostalAddress',
		'officeLocation': 'physicalDeliveryOfficeName',
		'preferredDeliveryMethod': 'preferredDeliveryMethod',
		'unixhome': 'homeDirectory',
		'shell': 'loginShell',
		'sambahome': 'sambaHomePath',
		'sambaUserWorkstations': 'sambaUserWorkstations',
		'sambaLogonHours': 'sambaLogonHours',
		'sambaPrivileges': 'univentionSambaPrivilegeList',
		'scriptpath': 'sambaLogonScript',
		'profilepath': 'sambaProfilePath',
		'homedrive': 'sambaHomeDrive',
		'gecos': 'gecos',
		'displayName': 'displayName',
		'birthday': 'univentionBirthday',
		'lastname': 'sn',
		'firstname': 'givenName',
		'userCertificate': 'userCertificate;binary',
		'jpegPhoto': 'jpegPhoto',
		'umcProperty': 'univentionUMCProperty',
		'lockedTime': 'sambaBadPasswordTime',
		'accountActivationDate': 'krb5ValidStart',
		'password': 'userPassword'
	}
	return create_udm_object(UDMOfficeUser, "udm_user_reference.pkl", user_mapping)


@pytest.fixture(scope='function')
def create_udm_group_object(mock_univention_libs):
	# type: (mock.MagicMock) -> Callable
	from univention.office365.udmwrapper.udmobjects import UDMOfficeGroup
	group_mapping = {
		'name': 'cn',
		'gidNumber': 'gidNumber',
		'description': 'description',
		'sambaGroupType': 'sambaGroupType',
		'mailAddress': 'mailPrimaryAddress',
		'adGroupType': 'univentionGroupType',
		'sambaPrivileges': 'univentionSambaPrivilegeList',
		'allowedEmailUsers': 'univentionAllowedEmailUsers',
		'allowedEmailGroups': 'univentionAllowedEmailGroups'
	}
	return create_udm_object(UDMOfficeGroup, "udm_group_reference.pkl", group_mapping)


@pytest.fixture
def transaction():
	# type: () -> List[Union[str,Dict]]
	return ['cn=asdasdasd', {}, {}, "a"]


@pytest.fixture
def deactivated_false():
	# type: () -> None
	with mock.patch('office365-user.is_deactivated_locked_or_expired', return_value=False):
		print("Mocked office365-user.is_deactivated_locked_or_expired to False")
		yield


@pytest.fixture
def deactivated_true():
	# type: () -> None
	with mock.patch('office365-user.is_deactivated_locked_or_expired', return_value=True):
		print("Mocked office365-user.is_deactivated_locked_or_expired to True")
		yield


# FIXME: it's repeated in test_udm_objects.py
@pytest.fixture(scope='function')
def udm_fake_user(mock_univention_libs):
	# type: (mock.MagicMock) -> "UDMOfficeUser"
	# Create replacement of the udm_user
	udm_user_dict = {
		"uid": "ontotest",
		"UniventionOffice365Data": "eJwVi0EOgjAQRa9CZm0NhRbBlVs3xitM22kyxs4YBDaEu1vzV+/l/R20H3zSgixwbXZYvzQ/Z5bIH3w/sFC1UFDqbpozR6r9OdFmVuGNZGGVinBqQMOL4nJP/8dkg8VAo+nIoXGDRzP6TGZC13aX1DuyLRzHD5ZvKC0=",
		"groups": ["cn=office365-users,cn=groups,cn=accounts,dc=example,dc=com"],
	}
	from univention.office365.udmwrapper.udmobjects import UDMOfficeUser
	udm_user = MagicMock(name="udm_fake_user", spec=UDMOfficeUser, autospec=True)
	udm_user.aliases.return_value = ["aliase1", "aliase2"]
	udm_user.__getitem__.side_effect = udm_user_dict.__getitem__
	udm_user.__setitem__.side_effect = udm_user_dict.__setitem__
	udm_user.update.side_effect = udm_user_dict.update
	return udm_user

@pytest.fixture(scope='function')
def udm_fake_user_old_listener(mock_univention_libs):
	# type: (mock.MagicMock) -> mock.MagicMock
	# Create replacement of the udm_user
	udm_user_dict = {
		"uid": "ontotest",
		"UniventionOffice365Data": "eJwVi0EOgjAQRa9CZm0NhRbBlVs3xitM22kyxs4YBDaEu1vzV+/l/R20H3zSgixwbXZYvzQ/Z5bIH3w/sFC1UFDqbpozR6r9OdFmVuGNZGGVinBqQMOL4nJP/8dkg8VAo+nIoXGDRzP6TGZC13aX1DuyLRzHD5ZvKC0=",
		"groups": ["cn=office365-users,cn=groups,cn=accounts,dc=example,dc=com"],
	}
	udm_user = MagicMock(name="udm_fake_user")
	udm_user.aliases.return_value = ["aliase1", "aliase2"]
	udm_user.__getitem__.side_effect = udm_user_dict.__getitem__
	udm_user.__setitem__.side_effect = udm_user_dict.__setitem__
	udm_user.update.side_effect = udm_user_dict.update
	return udm_user

@pytest.fixture
def function_params_01():
	# type: () -> List[Union[mock.MagicMock, str, Dict[str,List[bytes]], Dict[str,List[bytes]]]]
	ol = MagicMock()
	dn = "asdfasdf"
	new = {
		'uid': [b'justforTest'],
		'univentionOffice365Enabled': [b'1'],
		'univentionOffice365ADConnectionAlias': [b'o365domain']
	}
	old = {
		'uid': [b'justforTest2'],
		'univentionOffice365Enabled': [b'1'],
		'univentionOffice365ADConnectionAlias': [b'o365domain']
	}
	params = [
		ol,
		dn,
		new,
		old
	]
	return params


@pytest.fixture
def modify_user_function(office365_usr_lib):
	# type: (mock.MagicMock) -> mock.MagicMock
	old = office365_usr_lib.modify_user
	office365_usr_lib.modify_user = MagicMock()
	yield office365_usr_lib.modify_user
	office365_usr_lib.modify_user = old


@pytest.fixture
def new_user_function(office365_usr_lib):
	# type: (mock.MagicMock) -> mock.MagicMock
	old = office365_usr_lib.new_or_reactivate_user
	office365_usr_lib.new_or_reactivate_user = MagicMock()
	yield office365_usr_lib.new_or_reactivate_user
	office365_usr_lib.new_or_reactivate_user = old


@pytest.fixture
def delete_user_function(office365_usr_lib):
	# type: (mock.MagicMock) -> mock.MagicMock
	old = office365_usr_lib.delete_user
	office365_usr_lib.delete_user = MagicMock()
	yield office365_usr_lib.delete_user
	office365_usr_lib.delete_user = old


@pytest.fixture
def deactivate_user_function(office365_usr_lib):
	# type: (mock.MagicMock) -> mock.MagicMock
	old = office365_usr_lib.deactivate_user
	office365_usr_lib.deactivate_user = MagicMock()
	yield office365_usr_lib.deactivate_user
	office365_usr_lib.deactivate_user = old


@pytest.fixture
def all_user_functions(new_user_function, modify_user_function, delete_user_function, deactivate_user_function):
	# type: (mock.MagicMock, mock.MagicMock, mock.MagicMock, mock.MagicMock) -> List[mock.MagicMock]
	yield [
		new_user_function,
		modify_user_function,
		delete_user_function,
		deactivate_user_function
	]
