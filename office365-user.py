# -*- coding: utf-8 -*-
#
# Univention Microsoft 365 - listener module to provision accounts in MS Azure
#
# Copyright 2016-2019 Univention GmbH
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

from __future__ import absolute_import

import os
import json
import base64
import copy
import datetime
from stat import S_IRUSR, S_IWUSR

import listener
from univention.office365.azure_auth import AzureAuth, AzureADConnectionHandler, NoIDsStored, default_adconnection_alias_ucrv
from univention.office365.listener import Office365Listener, NoAllocatableSubscriptions, attributes_system, get_adconnection_filter
from univention.office365.udm_helper import UDMHelper
from univention.office365.logging2udebug import get_logger

listener.configRegistry.load()
attributes_anonymize = list()
attributes_mapping = dict()
attributes_never = list()
attributes_static = dict()
attributes_sync = list()
attributes_multiple_azure2ldap = dict()

logger = get_logger("office365", "o365")


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


not_migrated_to_v3 = listener.configRegistry.is_false('office365/migrate/adconnectionalias')

adconnection_aliases = AzureADConnectionHandler.get_adconnection_aliases()
initialized_adconnection = set([_ta for _ta in adconnection_aliases if AzureAuth.is_initialized(_ta)])

logger.info('Found AD connections in UCR: %r', adconnection_aliases)
logger.info('Found initialized AD connections: %r', initialized_adconnection)


name = 'office365-user'
description = 'sync users to office 365'
if initialized_adconnection:
	filter = '(&(objectClass=posixAccount)(objectClass=univentionOffice365)(uid=*){})'.format(get_adconnection_filter(listener.configRegistry, initialized_adconnection))
	logger.info("office 365 user listener active with filter=%r", filter)
else:
	filter = '(objectClass=deactivatedOffice365UserListener)'  # "objectClass" is indexed
	# filter = '(foo=bar)'  # TODO: remove me, probably the filter above should be the correct one
	logger.warn("office 365 user listener deactivated (no initialized AD connection)")
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
		if value is None or value.lower() in ("none", "0"):
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
	logger.info("office 365 user listener active with filter=%r", filter)
	logger.info('AD connection aliases: %r', adconnection_aliases)
	if not initialized_adconnection:
		raise RuntimeError("Microsoft 365 App ({}) not initialized for any AD connection yet, please run wizard.".format(name))


def clean():
	"""
	Remove  univentionOffice365ObjectID and univentionOffice365Data from all
	user objects.
	"""
	adconnection_filter = get_adconnection_filter(listener.configRegistry, initialized_adconnection)
	logger.info("Removing Microsoft 365 ObjectID and Data from all users (adconnection_filter=%r)...", adconnection_filter)
	UDMHelper.clean_udm_objects("users/user", listener.configRegistry["ldap/base"], ldap_cred, adconnection_filter)


def new_or_reactivate_user(ol, dn, new, old):
	try:
		new_user = ol.create_user(new)
	except NoAllocatableSubscriptions as exc:
		logger.error('{} ({})'.format(exc, exc.adconnection_alias))
		new_user = exc.user

	# save/update Azure objectId and object data in UDM object
	udm_user = ol.udm.get_udm_user(dn)
	if not_migrated_to_v3:
		udm_user["UniventionOffice365ObjectID"] = new_user["objectId"]
		udm_user["UniventionOffice365Data"] = Office365Listener.encode_o365data(new_user)
	else:
		new_azure_data = {
			ol.adconnection_alias: {
				'objectId': new_user['objectId'],
				'userPrincipalName': new_user['userPrincipalName'],
			}
		}
		old_azure_data_encoded = udm_user["UniventionOffice365Data"]
		if old_azure_data_encoded:
			# The account already has an Azure AD connection
			old_azure_data = Office365Listener.decode_o365data(old_azure_data_encoded)
			if 'objectId' in old_azure_data and not isinstance(old_azure_data['objectId'], dict):
				# Migration case
				old_azure_data = {
					k: v
					for k, v in old_azure_data.items()
					if isinstance(v, dict)
				}
			old_azure_data.update(new_azure_data)
			new_azure_data = old_azure_data
		udm_user["UniventionOffice365Data"] = Office365Listener.encode_o365data(new_azure_data)
		if not new.get('univentionOffice365ADConnectionAlias', []):
			udm_user["UniventionOffice365ADConnectionAlias"] = [ol.adconnection_alias]
	udm_user.modify()
	logger.info(
		"User creation success. userPrincipalName: %r objectId: %r dn: %s adconnection: %s",
		new_user["userPrincipalName"], new_user["objectId"], dn, ol.adconnection_alias
	)
	# update group membership for user on reactivation
	if new and old and listener.configRegistry.is_true("office365/groups/sync", False):
		for group in udm_user['groups']:
			logger.info('Need to add user to group %s.' % group)
			udm_grp = ol.udm.get_udm_group(group)
			if not udm_grp.get('UniventionOffice365Data') or ol.adconnection_alias not in Office365Listener.decode_o365data(udm_grp['UniventionOffice365Data']):
				logger.info('Need to create azure group %s for %s first.' % (group, ol.adconnection_alias))
				ol.create_groups(group, udm_grp.oldattr)
				udm_grp = ol.udm.get_udm_group(group)
			if udm_grp.get('UniventionOffice365Data'):
				azure_data = Office365Listener.decode_o365data(udm_grp['UniventionOffice365Data'])
				if ol.adconnection_alias in azure_data:
					if 'objectId' in azure_data[ol.adconnection_alias]:
						logger.info('Adding user %s to azure group %s' % (dn, group))
						ol.ah.add_objects_to_azure_group(azure_data[ol.adconnection_alias]['objectId'], [new_user["objectId"]])
				else:
					logger.error('Azure group %s not found at udm object.' % group)
			else:
				logger.error('UCS group %s is not synced to any azure ad.' % group)


def delete_user(ol, dn, new, old):
	ol.delete_user(old)
	logger.info("Deleted user %r adconnection: %s.", old["uid"][0], ol.adconnection_alias)


def deactivate_user(ol, dn, new, old):
	ol.deactivate_user(old or new)
	# remove userPrincipalName (or full Azure object data) from UDM object but keep objectId
	udm_user = ol.udm.get_udm_user(dn)
	if not_migrated_to_v3:
		udm_user["UniventionOffice365Data"] = None
		udm_user.modify()
	else:
		old_azure_data_encoded = udm_user["UniventionOffice365Data"]
		if old_azure_data_encoded:
			# The account already has an Azure AD connection
			old_azure_data = Office365Listener.decode_o365data(old_azure_data_encoded)
			try:
				del old_azure_data[ol.adconnection_alias]['userPrincipalName']
			except KeyError:
				pass
			udm_user["UniventionOffice365Data"] = Office365Listener.encode_o365data(old_azure_data)
			udm_user.modify()
	logger.info("Deactivated user %r adconnection: %s.", old["uid"][0], ol.adconnection_alias)


def modify_user(ol, dn, new, old):
	ol.modify_user(old, new)
	# update Azure object data in UDM object
	udm_user = ol.udm.get_udm_user(dn)
	azure_user = ol.get_user(old)
	if not_migrated_to_v3:
		udm_user["UniventionOffice365Data"] = Office365Listener.encode_o365data(azure_user)
	else:
		new_azure_data = {
			ol.adconnection_alias: {
				'objectId': azure_user['objectId'],
				'userPrincipalName': azure_user['userPrincipalName'],
			}
		}
		old_azure_data_encoded = udm_user["UniventionOffice365Data"]
		if old_azure_data_encoded:
			# The account already has an Azure AD connection
			old_azure_data = Office365Listener.decode_o365data(old_azure_data_encoded)
			if 'objectId' in old_azure_data and not isinstance(old_azure_data['objectId'], dict):
				# Migration case
				old_azure_data = {
					k: v
					for k, v in old_azure_data.items()
					if isinstance(v, dict)
				}
			old_azure_data.update(new_azure_data)
			new_azure_data = old_azure_data
		udm_user["UniventionOffice365Data"] = Office365Listener.encode_o365data(new_azure_data)
	udm_user.modify()
	logger.info("Modified user %r adconnection: %s.", old["uid"][0], ol.adconnection_alias)


def handler(dn, new, old, command):
	logger.debug("%s.handler() command: %r dn: %r", name, command, dn)
	if not initialized_adconnection:
		raise RuntimeError("{}.handler() Microsoft 365 App not initialized for any AD connection yet, please run wizard.".format(name))

	if command == 'r':
		save_old(old)
		return
	elif command == 'a':
		old = load_old(old)

	adconnection_aliases_old = set(old.get('univentionOffice365ADConnectionAlias', []))
	adconnection_aliases_new = set(new.get('univentionOffice365ADConnectionAlias', []))
	logger.info('adconnection_alias_old=%r adconnection_alias_new=%r', adconnection_aliases_old, adconnection_aliases_new)

	udm_helper = UDMHelper(ldap_cred)

	old_enabled = bool(int(old.get("univentionOffice365Enabled", ["0"])[0]))  # "" when disabled, "1" when enabled
	if old_enabled:
		udm_user = udm_helper.get_udm_user(dn, old)
		enabled = not is_deactived_locked_or_expired(udm_user)
		logger.debug("old was %s.", "enabled" if enabled else "deactivated, locked or expired")
		old_enabled &= enabled
		old_adconnection_enabled = adconnection_aliases_old.issubset(initialized_adconnection)
		logger.debug("old Azure AD connection is %s.", "enabled" if old_adconnection_enabled else "not initialized")
		old_enabled &= old_adconnection_enabled
	new_enabled = bool(int(new.get("univentionOffice365Enabled", ["0"])[0]))
	if new_enabled:
		udm_user = udm_helper.get_udm_user(dn, new)
		enabled = not is_deactived_locked_or_expired(udm_user)
		logger.debug("new is %s.", "enabled" if enabled else "deactivated, locked or expired")
		new_enabled &= enabled
		new_adconnection_enabled = adconnection_aliases_new.issubset(initialized_adconnection)
		logger.debug("new Azure AD connection is %s.", "enabled" if new_adconnection_enabled else "not initialized")
		new_enabled &= new_adconnection_enabled

	logger.debug("new_enabled=%r old_enabled=%r", new_enabled, old_enabled)

	#
	# Add or remove user from AD connections -> delete and create
	#
	if new_enabled and old_enabled:
		logger.info("new_enabled and adconnection_alias_old=%r and adconnection_alias_new=%r -> MODIFY (DELETE old, CREATE new) (%s)", adconnection_aliases_old, adconnection_aliases_new, dn)
		connections_to_be_deleted = adconnection_aliases_old - adconnection_aliases_new
		logger.info("DELETE (%s | %s)", connections_to_be_deleted, dn)
		for conn in connections_to_be_deleted:
			try:
				ol = Office365Listener(listener, name, _attrs, ldap_cred, dn, conn)
				delete_user(ol, dn, new, old)
			except NoIDsStored:
				logger.warn('Connection %r is not initialized, when trying to delete user %r. Ignoring.', conn, dn)

		connections_to_be_created = adconnection_aliases_new - adconnection_aliases_old
		logger.info("CREATE (%s | %s)", connections_to_be_created, dn)
		for conn in connections_to_be_created:
			try:
				ol = Office365Listener(listener, name, _attrs, ldap_cred, dn, conn)
				new_or_reactivate_user(ol, dn, new, old)
			except NoIDsStored:
				logger.warn('Connection %r is not initialized, when trying to create user %r. Ignoring.', conn, dn)

	#
	# NEW or REACTIVATED account
	#
	if new_enabled and not old_enabled:
		if listener.configRegistry.get(default_adconnection_alias_ucrv) in initialized_adconnection:
			# Migration script to App version 3 has not run - put user in default ad connection
			if not_migrated_to_v3:
				adconnection_aliases_new.add(listener.configRegistry.get(default_adconnection_alias_ucrv))

			# If no connection is set for a newly enabled object, and a default connection is configured via UCR,
			# add that default to the new object
			if not adconnection_aliases_new and listener.configRegistry.get(default_adconnection_alias_ucrv):
				logger.info("No ad connection defined, using default (%s | %s)", listener.configRegistry.get(default_adconnection_alias_ucrv), dn)
				adconnection_aliases_new.add(listener.configRegistry.get(default_adconnection_alias_ucrv))
		else:
			if not_migrated_to_v3 or (not adconnection_aliases_new and listener.configRegistry.get(default_adconnection_alias_ucrv)):
				logger.info("Cannot put user in default connection (%s), because it is not initialized", listener.configRegistry.get(default_adconnection_alias_ucrv))
				return

		if not adconnection_aliases_new:
			logger.info("No ad connection defined for new object, do nothing")
			return

		logger.info("new_enabled and not old_enabled -> NEW or REACTIVATED (%s | %s)", adconnection_aliases_new, dn)
		for conn in adconnection_aliases_new:
			ol = Office365Listener(listener, name, _attrs, ldap_cred, dn, conn)
			new_or_reactivate_user(ol, dn, new, old)
		return

	#
	# DELETE account
	#
	if old and not new:
		logger.info("old and not new -> DELETE (%s | %s)", adconnection_aliases_old, dn)
		for conn in adconnection_aliases_old:
			ol = Office365Listener(listener, name, _attrs, ldap_cred, dn, conn)
			delete_user(ol, dn, new, old)
		return

	#
	# DEACTIVATE account
	#
	if new and not new_enabled:
		logger.info("new and not new_enabled -> DEACTIVATE (%s | %s)", adconnection_aliases_old, dn)
		for conn in adconnection_aliases_old:
			ol = Office365Listener(listener, name, _attrs, ldap_cred, dn, conn)
			deactivate_user(ol, dn, new, old)
		return

	#
	# MODIFY account
	#
	if old_enabled and new_enabled:
		logger.info("old_enabled and new_enabled -> MODIFY (%s | %s)", adconnection_aliases_new, dn)
		for conn in adconnection_aliases_new:
			ol = Office365Listener(listener, name, _attrs, ldap_cred, dn, conn)
			modify_user(ol, dn, new, old)
		return
