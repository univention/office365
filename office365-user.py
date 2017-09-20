# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module to provision accounts in MS Azure
#
# Copyright 2016-2017 Univention GmbH
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


__package__ = ''  # workaround for PEP 366

import os
import json
import base64
import zlib
import copy
import datetime
from stat import S_IRUSR, S_IWUSR
from ldap.filter import filter_format

import listener
from univention.office365.azure_auth import AzureAuth, get_tenant_aliases
from univention.office365.listener import Office365Listener, NoAllocatableSubscriptions, attributes_system
from univention.office365.udm_helper import UDMHelper
from univention.office365.logging2udebug import get_logger


listener.configRegistry.load()
attributes_anonymize = list()
attributes_mapping = dict()
attributes_never = list()
attributes_static = dict()
attributes_sync = list()
attributes_multiple_azure2ldap = dict()
tenant_aliases = get_tenant_aliases()

logger = get_logger("office365", "o365")


def get_tenant_filter():
	resync_ucrv = 'office365/tenant/filter'
	ucr_value = listener.configRegistry[resync_ucrv] or ''
	aliases = ucr_value.strip().split()
	res = ''
	for alias in aliases:
		if alias not in tenant_aliases.keys():
			raise Exception('Tenant alias {!r} from office365/tenant/resync not listed in office365/tenant/alias/.* Exiting.'.format(alias))
		if not AzureAuth.is_initialized(alias):
			raise Exception('Tenant alias {!r} from office365/tenant/resync is not initialized. Existing.'.format(alias))
		res += filter_format('(univentionOffice365TenantAlias=%s)', (alias,))
	if len(res.split('=')) > 2:
		res = '(|{})'.format(res)
	logger.warn('Tenant filter is: %r', res)
	return res


def get_listener_attributes():
	global attributes_anonymize, attributes_mapping, attributes_never, attributes_static, attributes_sync

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

	attrs = set(attributes_system)
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
	for k, v in attributes_multiple_azure2ldap.items():
		if len(v) < 2:
			del attributes_multiple_azure2ldap[k]

	# sanity check
	no_mapping = [a for a in attrs if a not in attributes_mapping.keys() and a not in attributes_system]
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


name = 'office365-user'
description = 'sync users to office 365'
if any(AzureAuth.is_initialized(tenant_alias) for tenant_alias in tenant_aliases):
	filter = '(&(objectClass=univentionOffice365)(uid=*){})'.format(get_tenant_filter())
	logger.info("office 365 user listener active with filter=%r", filter)
else:
	filter = '(foo=bar)'
	logger.warn("office 365 user listener deactivated")
attributes = get_listener_attributes()
modrdn = "1"

OFFICE365_OLD_JSON = os.path.join("/var/lib/univention-office365", "office365-user_old_dn")

_attrs = dict(
	anonymize=attributes_anonymize,
	listener=copy.deepcopy(attributes),  # when handler() runs, all kinds of stuff is suddenly in attributes
	mapping=attributes_mapping,
	never=attributes_never,
	static=attributes_static,
	sync=attributes_sync,
	multiple=attributes_multiple_azure2ldap
)

ldap_cred = dict()

logger.info("listener observing attributes: %r", [a for a in attributes if a not in attributes_system])
logger.info("listener is also observing: %r", sorted(list(attributes_system)))
logger.info("attributes mapping UCS->AAD: %r", attributes_mapping)
logger.info("attributes to sync anonymized: %r", attributes_anonymize)
logger.info("attributes to never sync: %r", attributes_never)
logger.info("attributes to statically set in AAD: %r", attributes_static)
logger.info("attributes to sync: %r", attributes_sync)
logger.info("attributes to sync from multiple sources: %r", attributes_multiple_azure2ldap)
AzureAuth.get_http_proxies()  # log proxy settings


def load_old(old):
	try:
		with open(OFFICE365_OLD_JSON, "r") as fp:
			old = json.load(fp)
		old["krb5Key"] = [base64.b64decode(old["krb5Key"])]
		os.unlink(OFFICE365_OLD_JSON)
		return old
	except IOError:
		return old


def save_old(old):
	old["krb5Key"] = base64.b64encode(old["krb5Key"][0])
	with open(OFFICE365_OLD_JSON, "w+") as fp:
		os.chmod(OFFICE365_OLD_JSON, S_IRUSR | S_IWUSR)
		json.dump(old, fp)


def is_deactived_locked_or_expired(udm_user):
	"""
	Check if a LDAP-user is deactivated or locked (by any method: Windows/Kerberos/POSIX).

	:param udm_user: UDM user instance
	:return: bool: whether the user is deactivated or locked
	"""
	def boolify(value):
		if value is None or value.lower() == "none":
			return False
		return True

	if boolify(udm_user.info.get('disabled')) or boolify(udm_user.info.get('locked')):
		return True

	if udm_user.info.get('userexpiry'):
		try:
			if datetime.datetime.strptime(udm_user.info.get('userexpiry'), "%Y-%m-%d") <= datetime.datetime.now():
				return True
		except ValueError:
			logger.exception("Bad data in userexpiry: %r", udm_user.info.get('userexpiry'))
			return True

	return False


def setdata(key, value):
	global ldap_cred
	ldap_cred[key] = value


def initialize():
	if not AzureAuth.is_initialized():
		raise RuntimeError("Office 365 App not initialized yet, please run wizard.")


def clean():
	"""
	Remove  univentionOffice365ObjectID and univentionOffice365Data from all
	user objects.
	"""
	logger.info("Removing Office 365 ObjectID and Data from all users...")
	UDMHelper.clean_udm_objects("users/user", listener.configRegistry["ldap/base"], ldap_cred)


def handler(dn, new, old, command):
	logger.debug("%s.handler() command: %r dn: %r", name, command, dn)
	if not AzureAuth.is_initialized():
		raise RuntimeError("{}.handler() Office 365 App not initialized yet, please run wizard.".format(name))
	else:
		pass

	if command == 'r':
		save_old(old)
		return
	elif command == 'a':
		old = load_old(old)

	ol = Office365Listener(listener, name, _attrs, ldap_cred, dn)

	old_enabled = bool(int(old.get("univentionOffice365Enabled", ["0"])[0]))  # "" when disabled, "1" when enabled
	if old_enabled:
		udm_user = ol.udm.get_udm_user(dn, old)
		enabled = not is_deactived_locked_or_expired(udm_user)
		logger.debug("old was %s.", "enabled" if enabled else "deactivated, locked or expired")
		old_enabled &= enabled
	new_enabled = bool(int(new.get("univentionOffice365Enabled", ["0"])[0]))
	if new_enabled:
		udm_user = ol.udm.get_udm_user(dn, new)
		enabled = not is_deactived_locked_or_expired(udm_user)
		logger.debug("new is %s.", "enabled" if enabled else "deactivated, locked or expired")
		new_enabled &= enabled

	#
	# NEW or REACTIVATED account
	#
	if new_enabled and not old_enabled:
		logger.debug("new_enabled and not old_enabled -> NEW or REACTIVATED (%s)", dn)
		try:
			new_user = ol.create_user(new)
		except NoAllocatableSubscriptions as exc:
			logger.error(str(exc))
			new_user = exc.user
		# save/update Azure objectId and object data in UDM object
		udm_user = ol.udm.get_udm_user(dn)
		udm_user["UniventionOffice365ObjectID"] = new_user["objectId"]
		udm_user["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(new_user))).rstrip()
		udm_user.modify()
		logger.info(
			"User creation success. userPrincipalName: %r objectId: %r dn: %s",
			new_user["userPrincipalName"],
			new_user["objectId"], dn
		)
		return

	#
	# DELETE account
	#
	if old and not new:
		logger.debug("old and not new -> DELETE (%s)", dn)
		ol.delete_user(old)
		logger.info("Deleted user %r.", old["uid"][0])
		return

	#
	# DEACTIVATE account
	#
	if new and not new_enabled:
		logger.debug("new and not new_enabled -> DEACTIVATE (%s)", dn)
		ol.deactivate_user(old)
		# update Azure objectId and object data in UDM object
		udm_user = ol.udm.get_udm_user(dn)
		# Cannot delete UniventionOffice365Data, because it would result in:
		# ldapError: Inappropriate matching: modify/delete: univentionOffice365Data: no equality matching rule
		# Explanation: http://gcolpart.evolix.net/blog21/delete-facsimiletelephonenumber-attribute/
		udm_user["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(None))).rstrip()
		udm_user.modify()
		logger.info("Deactivated user %r.", old["uid"][0])
		return

	#
	# MODIFY account
	#
	if old_enabled and new_enabled:
		logger.debug("old_enabled and new_enabled -> MODIFY (%s)", dn)
		ol.modify_user(old, new)
		# update Azure object data in UDM object
		udm_user = ol.udm.get_udm_user(dn)
		azure_user = ol.get_user(old)
		udm_user["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(azure_user))).rstrip()
		udm_user.modify()
		logger.info("Modified user %r.", old["uid"][0])
		return
