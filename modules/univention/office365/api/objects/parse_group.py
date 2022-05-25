import os
import pickle
from collections import UserDict
from pprint import pprint

import mock

import univention.office365.mocking

from univention.office365.api.objects.azureobjects import GroupAzure
from univention.office365.api.objects.udmobjects import UDMOfficeGroup


def parse(udm_group, modify= False):
	# type: (UDMOfficeGroup, bool) -> GroupAzure
	# anonymize > static > sync
	# get values to sync
	# core = self.cores[udm_user.current_connection_alias]  # type: MSGraphApiCore

	data = dict(description=udm_group.description,
			displayName=udm_group.cn,
			mailEnabled=False,
			mailNickname=udm_group.cn.replace(" ", "_-_"),
			securityEnabled=True)
	group_azure = GroupAzure(**data)
	return group_azure


def create_udm_object(cls, file):

	mapping = {
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

	unmapName = {v:k for k,v in mapping.items()}
	def _create_udm_object():
		test_path = "/home/ivan/univention/components/office365/test"
		udm_object_reference = pickle.load(open(os.path.join(test_path, "udm_pkl", file), "rb"))
		pprint(udm_object_reference)
		ldap_dict = udm_object_reference["oldattr"]
		udm_object = cls(ldap_dict, {}, dn='cn=test,dc=test,dc=test')
		udm_object.udm_object_reference = UserDict(udm_object_reference)
		udm_object.udm_object_reference.modify = mock.MagicMock()
		udm_object.udm_object_reference.oldattr = ldap_dict
		udm_object.udm_object_reference.mapping = mock.MagicMock()
		udm_object.udm_object_reference.mapping.unmapName = lambda x: unmapName[x] if x in unmapName else ""
		return udm_object
	return _create_udm_object


def create_udm_user_object():
	return create_udm_object(UDMOfficeGroup, "udm_group_reference.pkl")()

if __name__ == '__main__':
	udm_user = create_udm_user_object()
	# ldap_dict.update(dict(ldap_cred={},  adconnection_alias=["hola"]))
	azure_user = parse(udm_user, modify=True)
	print(azure_user.get_not_none_values_as_dict())
