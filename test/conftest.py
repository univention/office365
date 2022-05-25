import importlib
import os
import pickle
import sys
from collections import UserDict

import pytest
from mock import mock
from mock.mock import MagicMock
from six import text_type
import importlib
import os
import pickle
import sys
from collections import UserDict

import pytest
from mock import mock
from mock.mock import MagicMock
from six import text_type


ldap_cred = {}

@pytest.fixture(scope='session')
def mock_univention_libs():
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

	unmapName = {v: k for k, v in mapping.items()}
	def _create_udm_object():
		test_path = os.path.dirname(os.path.abspath(__file__))
		udm_object_reference = pickle.load(open(os.path.join(test_path, "udm_pkl", file), "rb"))
		ldap_dict = udm_object_reference["oldattr"]
		udm_object = cls(ldap_dict, {}, dn='cn=test,dc=test,dc=test')
		udm_object.udm_object_reference = UserDict(udm_object_reference)
		udm_object.udm_object_reference.modify = mock.MagicMock()
		udm_object.udm_object_reference.oldattr = ldap_dict
		udm_object.udm_object_reference.mapping = mock.MagicMock()
		udm_object.udm_object_reference.mapping.unmapName = lambda x: unmapName[x] if x in unmapName else ""
		udm_object.udm_object_reference.get_usage_location = mock.MagicMock(return_value="DE")
		udm_object.udm_object_reference["groups"] = ["cn=test,dc=test,dc=test"]
		return udm_object
	return _create_udm_object


@pytest.fixture(scope='function')
def udm_object(mock_univention_libs):
	from univention.office365.api.objects.udmobjects import UDMOfficeObject
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
		'physicalDeliveryOfficeName': 'physicalDeliveryOfficeName',
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
	from univention.office365.api.objects.udmobjects import UDMOfficeUser
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
		'physicalDeliveryOfficeName': 'physicalDeliveryOfficeName',
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
	from univention.office365.api.objects.udmobjects import UDMOfficeGroup
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

@pytest.fixture
def handler_parameters():
	# read pickel file from tmp office
	import pickle
	files_path = os.path.join("/tmp/office365/")
	files_to_read = os.listdir(files_path)
	for file in files_to_read:
		yield pickle.load(open(os.path.join(files_path, file), "rb"))

@pytest.fixture(scope='module', autouse=True)
def office365_usr_lib(mock_univention_libs):
	office365_usr_lib = importlib.import_module('office365-user')
	office365_usr_lib.adconnection_aliases = {'o365domain'}
	return office365_usr_lib


@pytest.fixture(scope='module', autouse=True)
def office365_group_lib(mock_univention_libs):
	office365_group_lib = importlib.import_module('office365-group')
	office365_group_lib.adconnection_aliases = {'o365domain'}
	return office365_group_lib


# @pytest.fixture(scope='module', autouse=True)
# def office365_user_listener(mock_univention_libs):
# 	sys.modules['univention.admin.uldap'] = MagicMock()
# 	sys.modules['univention.admin.uldap'].access = MagicMock()
# 	sys.modules['univention.admin.uldap'].position = MagicMock()
# 	sys.modules['inspect'].getfile = MagicMock(side_effect=lambda x: '/usr/lib/univention-directory-listener' )
# 	import office365_user_listener
# 	return office365_user_listener

@pytest.fixture
def group_initialized_adconnection_default(office365_group_lib):
	old = office365_group_lib.initialized_adconnections
	office365_group_lib.initialized_adconnections = ['o365domain', 'azuretestdomain', 'defaultdomainfortest']
	yield
	office365_group_lib.initialized_adconnections = old


@pytest.fixture
def transaction():
	return ['cn=asdasdasd', {}, {}, "a"]



@pytest.fixture
def initialized_adconnection_none(office365_usr_lib):
	old = office365_usr_lib.initialized_adconnection
	office365_usr_lib.adconnection = None
	yield
	office365_usr_lib.initialized_adconnection = old


@pytest.fixture
def initialized_adconnection_default(office365_usr_lib):
	old = office365_usr_lib.initialized_adconnection
	office365_usr_lib.initialized_adconnection = ['o365domain', 'azuretestdomain', 'defaultdomainfortest']
	yield
	office365_usr_lib.initialized_adconnection = old


@pytest.fixture
def deactivated_false():
	with mock.patch('office365-user.is_deactivated_locked_or_expired', return_value=False):
		print("Mocked office365-user.is_deactivated_locked_or_expired to False")
		yield


@pytest.fixture
def deactivated_true():
	with mock.patch('office365-user.is_deactivated_locked_or_expired', return_value=True):
		print("Mocked office365-user.is_deactivated_locked_or_expired to True")
		yield


# FIXME: it's repeated in test_udm_objects.py
@pytest.fixture(scope='function')
def udm_fake_user(mock_univention_libs):
	# Create replacement of the udm_user
	udm_user_dict = {
		"uid": "ontotest",
		"UniventionOffice365Data": "eJwVi0EOgjAQRa9CZm0NhRbBlVs3xitM22kyxs4YBDaEu1vzV+/l/R20H3zSgixwbXZYvzQ/Z5bIH3w/sFC1UFDqbpozR6r9OdFmVuGNZGGVinBqQMOL4nJP/8dkg8VAo+nIoXGDRzP6TGZC13aX1DuyLRzHD5ZvKC0=",
		"groups": ["cn=office365-users,cn=groups,cn=accounts,dc=example,dc=com"],
	}
	from univention.office365.api.objects.udmobjects import UDMOfficeUser
	udm_user = MagicMock(name="udm_fake_user", spec=UDMOfficeUser, autospec=True)
	udm_user.aliases.return_value = ["aliase1", "aliase2"]
	udm_user.__getitem__.side_effect = udm_user_dict.__getitem__
	udm_user.__setitem__.side_effect = udm_user_dict.__setitem__
	udm_user.update.side_effect = udm_user_dict.update
	return udm_user

@pytest.fixture(scope='function')
def udm_fake_user_old_listener(mock_univention_libs):
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
	old = office365_usr_lib.modify_user
	office365_usr_lib.modify_user = MagicMock()
	yield office365_usr_lib.modify_user
	office365_usr_lib.modify_user = old


@pytest.fixture
def new_user_function(office365_usr_lib):
	old = office365_usr_lib.new_or_reactivate_user
	office365_usr_lib.new_or_reactivate_user = MagicMock()
	yield office365_usr_lib.new_or_reactivate_user
	office365_usr_lib.new_or_reactivate_user = old


@pytest.fixture
def delete_user_function(office365_usr_lib):
	old = office365_usr_lib.delete_user
	office365_usr_lib.delete_user = MagicMock()
	yield office365_usr_lib.delete_user
	office365_usr_lib.delete_user = old


@pytest.fixture
def deactivate_user_function(office365_usr_lib):
	old = office365_usr_lib.deactivate_user
	office365_usr_lib.deactivate_user = MagicMock()
	yield office365_usr_lib.deactivate_user
	office365_usr_lib.deactivate_user = old


@pytest.fixture
def all_user_functions(new_user_function, modify_user_function, delete_user_function, deactivate_user_function):
	yield [
		new_user_function,
		modify_user_function,
		delete_user_function,
		deactivate_user_function
	]
