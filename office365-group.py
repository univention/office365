# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module to manage groups in MS Azure
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

import base64
import copy
import json
import os
from stat import S_IRUSR, S_IWUSR

import listener
from univention.office365.azure_auth import AzureAuth, AzureADConnectionHandler
from univention.office365.listener import Office365Listener, get_adconnection_filter
from univention.office365.udm_helper import UDMHelper
from univention.office365.logging2udebug import get_logger


logger = get_logger("office365", "o365")
listener.configRegistry.load()
adconnection_aliases = AzureADConnectionHandler.get_adconnection_aliases()
initialized_adconnections = [_ta for _ta in adconnection_aliases if AzureAuth.is_initialized(_ta)]

logger.info('Found adconnections in UCR: %r', adconnection_aliases)
logger.info('Found initialized adconnections: %r', initialized_adconnections)


name = 'office365-group'
description = 'sync groups to office 365'
if not listener.configRegistry.is_true("office365/groups/sync", False):
	filter = '(objectClass=deactivatedOffice365GroupListener)'  # "objectClass" is indexed
	logger.warn("office 365 group listener deactivated by UCR office365/groups/sync")
elif initialized_adconnections:
	filter = '(&(objectClass=posixGroup)(objectClass=univentionOffice365){})'.format(get_adconnection_filter(listener.configRegistry, adconnection_aliases))
	logger.info("office 365 group listener active with filter=%r", filter)
else:
	filter = '(objectClass=deactivatedOffice365GroupListener)'
	logger.warn("office 365 group listener deactivated (no initialized adconnections)")
attributes = ["cn", "description", "uniqueMember"]
modrdn = "1"

OFFICE365_OLD_JSON = os.path.join("/var/lib/univention-office365", "office365-group_old_dn")

ldap_cred = dict()
attributes_copy = copy.deepcopy(attributes)  # when handler() runs, all kinds of stuff is suddenly in attributes


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


def setdata(key, value):
	global ldap_cred
	ldap_cred[key] = value


def initialize():
	if not listener.configRegistry.is_true("office365/groups/sync", False):
		raise RuntimeError("Office 365 App: syncing of groups is deactivated by UCR.")

	if not initialized_adconnections:
		raise RuntimeError("Office 365 App ({}) not initialized for any Azure AD connection yet, please run wizard.".format(name))


def clean():
	"""
	Remove  univentionOffice365ObjectID and univentionOffice365Data from all
	user objects.
	"""
	adconnection_filter = get_adconnection_filter(listener.configRegistry, adconnection_aliases)
	logger.info("Removing Office 365 ObjectID and Data from all users (adconnection_filter=%r)...", adconnection_filter)
	UDMHelper.clean_udm_objects("groups/group", listener.configRegistry["ldap/base"], ldap_cred, adconnection_filter)


def create_groups(ol, dn, new, old):
	for groupdn in ol.udm.udm_groups_with_azure_users(dn):
		new_group = ol.create_group_from_ldap(groupdn)
		# save Azure objectId in UDM object
		udm_group = ol.udm.get_udm_group(dn)
		if listener.configRegistry.is_false('office365/migrate/adconnectionalias'):
			udm_group["UniventionOffice365ObjectID"] = new_group["objectId"]
		else:
			new_azure_data = {ol.adconnection_alias: new_group}
			old_azure_data_encoded = udm_group["UniventionOffice365Data"]
			if old_azure_data_encoded:
				# The account already has an Azure AD connection
				old_azure_data = Office365Listener.decode_o365data(old_azure_data_encoded)
				new_azure_data = old_azure_data.update(new_azure_data)
			new_group["UniventionOffice365Data"] = Office365Listener.encode_o365data(new_azure_data)
		udm_group.modify()
		logger.info("Created group with displayName: %r (%r) adconnection: %s", new_group["displayName"], new_group["objectId"], ol.adconnection_alias)


def handler(dn, new, old, command):
	logger.debug("%s.handler() command: %r dn: %r", name, command, dn)
	if not listener.configRegistry.is_true("office365/groups/sync", False):
		return
	if not initialized_adconnections:
		raise RuntimeError("{}.handler() Office 365 App not initialized for any Azure AD connection yet, please run wizard.".format(name))

	if command == 'r':
		save_old(old)
		return
	elif command == 'a':
		old = load_old(old)

	adconnection_aliases_old = set(old.get('univentionOffice365ADConnectionAlias', []))
	adconnection_aliases_new = set(new.get('univentionOffice365ADConnectionAlias', []))
	logger.info('adconnection_alias_old=%r adconnection_alias_new=%r', adconnection_aliases_old, adconnection_aliases_new)

	old_enabled = bool(int(old.get("univentionOffice365Enabled", ["0"])[0]))
	if old_enabled:
		old_adconnection_enabled = adconnection_aliases_old.issubset(initialized_adconnections)
		logger.debug("old Azure AD connection is %s.", "enabled" if old_adconnection_enabled else "not initialized")
		old_enabled &= old_adconnection_enabled

	new_enabled = bool(int(new.get("univentionOffice365Enabled", ["0"])[0]))
	if new_enabled:
		new_adconnection_enabled = adconnection_aliases_new.issubset(initialized_adconnections)
		logger.debug("new Azure AD connection is %s.", "enabled" if new_adconnection_enabled else "not initialized")
		new_enabled &= new_adconnection_enabled

	logger.debug("new_enabled=%r old_enabled=%r", new_enabled, old_enabled)

	if new_enabled and old_enabled:
		logger.info("new_enabled and adconnection_alias_old=%r and adconnection_alias_new=%r -> MODIFY (DELETE old, CREATE new) (%s)", adconnection_aliases_old, adconnection_aliases_new, dn)
		connections_to_be_deleted = adconnection_aliases_old - adconnection_aliases_new
		logger.info("DELETE (%s | %s)", connections_to_be_deleted, dn)
		for conn in connections_to_be_deleted:
			ol = Office365Listener(listener, name, dict(listener=attributes_copy), ldap_cred, dn, conn)
			ol.delete_group(dn)

		connections_to_be_created = adconnection_aliases_new - adconnection_aliases_old
		logger.info("CREATE (%s | %s)", connections_to_be_created, dn)
		for conn in connections_to_be_created:
			ol = Office365Listener(listener, name, dict(listener=attributes_copy), ldap_cred, dn, conn)
			create_groups(ol, dn, new, old)

	#
	# NEW group
	#
	if new and new_enabled and not old:
		logger.debug("new and not old -> NEW (%s)", dn)
		for conn in adconnection_aliases_new:
			ol = Office365Listener(listener, name, dict(listener=attributes_copy), ldap_cred, dn, conn)
			create_groups(ol, dn, new, old)
		logger.debug("done (%s)", dn)
		return

	#
	# DELETE group
	#
	if old and old_enabled and not new:
		logger.debug("old and not new -> DELETE (%s)", dn)
		for conn in adconnection_aliases_old:
			ol = Office365Listener(listener, name, dict(listener=attributes_copy), ldap_cred, dn, conn)
			ol.delete_group(dn)
			logger.info("Deleted group %r (%r).", old["cn"][0], conn)
		return

	#
	# MODIFY group
	#
	if old and new and new_enabled:
		logger.debug("old and new -> MODIFY (%s)", dn)
		for conn in adconnection_aliases_new:
			ol = Office365Listener(listener, name, dict(listener=attributes_copy), ldap_cred, dn, conn)
			azure_group = ol.modify_group(old, new)
			# save Azure objectId in UDM object
			try:
				object_id = azure_group["objectId"]
			except TypeError:
				# None -> group was deleted
				object_id = None
			udm_group = ol.udm.get_udm_group(dn)
			udm_group["UniventionOffice365ObjectID"] = object_id
			udm_group.modify()

			logger.info("Modified group %r (%r).", old["cn"][0], object_id)
		return
