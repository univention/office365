import base64
import os
import pickle
import typing
from collections import UserDict
from pprint import pprint

import mock

import univention.office365.mocking
import copy
import uuid

import univention
import listener

from univention.office365.api.objects.connector import ConnectorAttributes
from univention.office365.api.objects.utils import create_random_pw
from univention.office365.api_helper import get_http_proxies
from univention.office365.logging2udebug import get_logger
from univention.office365.api.objects.azureobjects import UserAzure
from univention.office365.api.objects.udmobjects import UDMOfficeUser

listener.configRegistry.load()
attributes_anonymize = list()
attributes_mapping = dict()
attributes_never = list()
attributes_static = dict()
attributes_sync = list()
attributes_multiple_azure2ldap = dict()

logger = get_logger("office365", "o365")

attributes_system_to_skip = {
	"krb5KDCFlags"
	"krb5PasswordEnd",
	"krb5ValidEnd",
	"passwordexpiry",
	"sambaAcctFlags",
	"sambaKickoffTime",
	"shadowExpire",
	"shadowLastChange",
	"shadowMax",
	"univentionMicrosoft365Team",
	"univentionOffice365Enabled",
	"univentionOffice365ADConnectionAlias",
	"userexpiry",
	"userPassword"
}
skiping_fields = {"dn", "other", "username", "locked", "deactivated", "adconnection_alias"}


def get_listener_attributes():
	global attributes_anonymize, attributes_mapping, attributes_never, attributes_static, attributes_sync, attributes_multiple_azure2ldap

	def rm_objs_from_list_or_dict(rm_objs_list, list_of_listsdicts):
		for rm_obj in rm_objs_list:
			for obj in list_of_listsdicts:
				if isinstance(obj, list):
					try:
						obj.remove(rm_obj)
					except ValueError:
						pass
				elif isinstance(obj, dict):
					try:
						del obj[rm_obj]
					except KeyError:
						pass
				else:
					raise ValueError("Can only deal with dicts and lists: rm_objs_from_list_or_dict({}, {})".format(
						rm_objs_list, list_of_listsdicts))

	attrs = set(attributes_system_to_skip)
	for k, v in listener.configRegistry.items():
		if k == "office365/attributes/anonymize":
			attributes_anonymize = [x.strip() for x in v.split(",") if x.strip()]
			attrs.update(attributes_anonymize)
		elif k.startswith("office365/attributes/mapping/"):
			at = k.split("/")[-1]
			attributes_mapping[at] = v.strip()
		elif k == "office365/attributes/never":
			attributes_never = [x.strip() for x in v.split(",") if x.strip()]
		elif k.startswith("office365/attributes/static/"):
			at = k.split("/")[-1]
			attributes_static[at] = v.strip()
			attrs.add(at)
		elif k == "office365/attributes/sync":
			attributes_sync = [x.strip() for x in v.split(",") if x.strip()]
			attrs.update(attributes_sync)
		else:
			pass
	attrs = list(attrs)

	# never > anonymize > static > sync
	rm_objs_from_list_or_dict(attributes_never, [attrs, attributes_anonymize, attributes_static, attributes_sync])
	rm_objs_from_list_or_dict(attributes_anonymize, [attributes_static, attributes_sync])
	rm_objs_from_list_or_dict(attributes_static, [attributes_sync])

	# find attributes that map to the same azure properties
	for k, v in attributes_mapping.items():
		try:
			attributes_multiple_azure2ldap[v].append(k)
		except KeyError:
			attributes_multiple_azure2ldap[v] = [k]
	attributes_multiple_azure2ldap = {k: v for k, v in attributes_multiple_azure2ldap.items() if len(v) >= 2}

	# sanity check
	no_mapping = [a for a in attrs if a not in attributes_mapping.keys() and a not in attributes_system_to_skip]
	if no_mapping:
		logger.warn("No mappings for attributes %r found - ignoring.", no_mapping)
		rm_objs_from_list_or_dict(no_mapping, [attrs, attributes_anonymize, attributes_static, attributes_sync])

	if "univentionOffice365ObjectID" in attrs or "UniventionOffice365Data" in attrs:
		logger.warn("Nice try.")
		rm_objs_from_list_or_dict(
			["univentionOffice365ObjectID", "univentionOffice365Data"],
			[attrs, attributes_anonymize, attributes_static, attributes_sync]
		)

	# just for log readability
	attrs.sort()
	attributes_anonymize.sort()
	attributes_never.sort()
	attributes_sync.sort()

	return attrs


attributes = get_listener_attributes()

# _attrs = dict(
# 	anonymize=attributes_anonymize,
# 	listener=copy.copy(attributes),  # when handler() runs, all kinds of stuff is suddenly in attributes
# 	mapping=attributes_mapping,
# 	never=attributes_never,
# 	static=attributes_static,
# 	sync=attributes_sync,
# 	multiple=attributes_multiple_azure2ldap
# )

_attrs = {
	'system': attributes_system_to_skip,
	'anonymize': [],
		  'listener': ['displayName',
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
					   'userexpiry'],
		  'mapping': {'displayName': 'displayName',
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
		  'never': [],
		  'static': {},
		  'sync': ['displayName',
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
				   'telephoneNumber'],
		  'multiple': {'otherMails': ['mail',
									  'mailAlternativeAddress',
									  'mailPrimaryAddress']}
		  }

ldap_cred = {}

logger.info("listener observing attributes: %r", [a for a in attributes if a not in attributes_system_to_skip])
logger.info("listener is also observing: %r", sorted(list(attributes_system_to_skip)))
logger.info("attributes mapping UCS->AAD: %r", attributes_mapping)
logger.info("attributes to sync anonymized: %r", attributes_anonymize)
logger.info("attributes to never sync: %r", attributes_never)
logger.info("attributes to statically set in AAD: %r", attributes_static)
logger.info("attributes to sync: %r", attributes_sync)
logger.info("attributes to sync from multiple sources: %r", attributes_multiple_azure2ldap)
# get_http_proxies(listener.configRegistry, logger)


def anonymize(value):  # type: (List[str]) -> str
	# FIXME: txt is unused
	return uuid.uuid4().hex


def parse(udm_user, modify= False):
	# type: (UDMOfficeUser, bool) -> UserAzure
	# anonymize > static > sync
	# get values to sync
	res = dict()
	# core = self.cores[udm_user.current_connection_alias]  # type: MSGraphApiCore

	for attr in _attrs["listener"]:
		if attr in _attrs["system"]:
			# filter out univentionOffice365Enabled and account deactivation/locking attributes
			continue
		elif attr not in udm_user.udm_object_reference.oldattr and not modify:
			# only set empty values to unset properties when modifying
			continue
		elif attr in _attrs["anonymize"]:
			tmp = anonymize(getattr(udm_user, attr))
		elif attr in _attrs["static"]:
			tmp = _attrs["static"][attr]
		elif attr in _attrs["sync"]:
			tmp = getattr(udm_user, attr)  # Azure does not like empty strings - it wants None!
		else:
			raise RuntimeError("Attribute to sync {!r} is not configured through UCR.".format(attr))

		if attr in res:
			if isinstance(res[attr], list):
				res[attr].append(tmp)
			else:
				raise RuntimeError("Office365Listener._get_sync_values() res[{}] already exists with type {} and value '{}'.".format(attr, type(res[attr]), res[attr]))
		else:
			# if hasattr(tmp, '__len__'):
			# 	if tmp and len(tmp) == 1:
			# 		res[attr] = tmp[0]
			# 	else:
			# 		res[attr] = tmp
			# else:
			res[attr] = tmp

	# build data dict to build AzureObject
	data = {}
	user_azure_fields = UserAzure.get_fields()
	for udm_key, azure_key in _attrs["mapping"].items():
		if udm_key in res:
			value = res.get(udm_key)
			if azure_key in list(_attrs["multiple"].keys()):
				if isinstance(value, list):
					if azure_key not in data:
						data[azure_key] = value
					else:
						data[azure_key].extend(value)
				else:
					if azure_key not in data:
						data[azure_key] = [value]
					else:
						data[azure_key].append(value)
			elif (user_azure_fields.get(azure_key) == list and not isinstance(value, list)):
				if azure_key not in data:
					data[azure_key] = [value]
				else:
					data[azure_key].append(value)
			else:
				if not isinstance(value, user_azure_fields.get(azure_key)):
					print(f"Warning not same type {azure_key}: {value} not is a {user_azure_fields.get(azure_key)}")
					if hasattr(value, "__len__"):
						if len(value) == 0:
							value = None
							continue
						elif len(value) == 1:
							value = value[0]
						else:
							value = value[0]
				if hasattr(value, "__len__"):
					if len(value) == 0:
						value = None
						continue
				data[azure_key] = value

	# mandatory attributes, not to be overwritten by user
	local_part_of_email_address = udm_user.mailPrimaryAddress.rpartition("@")[0]
	mandatory_attributes = dict(onPremisesImmutableId=udm_user.entryUUID,
								accountEnabled=True,
								passwordProfile=dict(password=create_random_pw(),
													 forceChangePasswordNextLogin=False),
								userPrincipalName="{0}@{1}".format(local_part_of_email_address, "test_domain"), #core.account["domain"]),
								mailNickname=local_part_of_email_address,
								displayName=data.get("displayName", "no name"),
								usageLocation="PATATA", )  # udm_user.get_usage_location(), )
	data.update(mandatory_attributes)
	user_azure = UserAzure(**data)
	return user_azure

def create_udm_object(cls, file):

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
	return create_udm_object(UDMOfficeUser, "udm_user_reference.pkl")()

if __name__ == '__main__':
	udm_user = create_udm_user_object()
	# ldap_dict.update(dict(ldap_cred={},  adconnection_alias=["hola"]))
	azure_user = parse(udm_user, modify=True)
	print(azure_user.get_not_none_values_as_dict())
