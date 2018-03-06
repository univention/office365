# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module to manage groups in MS Azure
#
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


__package__ = ''  # workaround for PEP 366

import os
import json
import base64
import copy
from stat import S_IRUSR, S_IWUSR

import listener
from univention.office365.azure_auth import AzureAuth
from univention.office365.listener import Office365Listener
from univention.office365.udm_helper import UDMHelper
from univention.office365.logging2udebug import get_logger


logger = get_logger("office365", "o365")
listener.configRegistry.load()


name = 'office365-group'
description = 'sync groups to office 365'
if not listener.configRegistry.is_true("office365/groups/sync", False):
	filter = '(objectClass=deactivatedOffice365GroupListener)'  # "objectClass" is indexed
	logger.warn("office 365 group listener deactivated by UCR office365/groups/sync")
elif AzureAuth.is_initialized():
	filter = '(objectClass=posixGroup)'
	logger.info("office 365 group listener active")
else:
	filter = '(objectClass=deactivatedOffice365GroupListener)'
	logger.warn("office 365 group listener deactivated (not yet initialized)")
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

	if not AzureAuth.is_initialized():
		raise RuntimeError("Office 365 App ({}) not initialized yet, please run wizard.".format(name))


def clean():
	"""
	Remove  univentionOffice365ObjectID and univentionOffice365Data from all
	user objects.
	"""
	logger.info("Removing Office 365 ObjectID and Data from all groups.")
	UDMHelper.clean_udm_objects("groups/group", listener.configRegistry["ldap/base"], ldap_cred)


def create_groups(ol, dn):
	for groupdn in ol.udm.udm_groups_with_azure_users(dn):
		new_group = ol.create_group_from_ldap(groupdn)
		# save Azure objectId in UDM object
		udm_group = ol.udm.get_udm_group(dn)
		udm_group["UniventionOffice365ObjectID"] = new_group["objectId"]
		udm_group.modify()
		logger.info("Created group with displayName: %r (%r)", new_group["displayName"], new_group["objectId"])


def handler(dn, new, old, command):
	logger.debug("%s.handler() command: %r dn: %r", name, command, dn)
	if not listener.configRegistry.is_true("office365/groups/sync", False):
		return
	if not AzureAuth.is_initialized():
		raise RuntimeError("{}.handler() Office 365 App not initialized yet, please run wizard.".format(name))

	if command == 'r':
		save_old(old)
		return
	elif command == 'a':
		old = load_old(old)

	ol = Office365Listener(listener, name, dict(listener=attributes_copy), ldap_cred, dn)

	#
	# NEW group
	#
	if new and not old:
		logger.debug("new and not old -> NEW (%s)", dn)
		create_groups(ol, dn)
		logger.debug("done (%s)", dn)
		return

	#
	# DELETE group
	#
	if old and not new:
		logger.debug("old and not new -> DELETE (%s)", dn)
		if "univentionOffice365ObjectID" in old:
			ol.delete_group(old)
			logger.info("Deleted group %r (%r).", old["cn"][0], old["univentionOffice365ObjectID"][0])
		return

	#
	# MODIFY group
	#
	if old and new:
		logger.debug("old and new -> MODIFY (%s)", dn)
		if "univentionOffice365ObjectID" in old:
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
		else:
			create_groups(ol, dn)
		return
