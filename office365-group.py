# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module to manage groups in MS Azure
#
# Copyright 2016 Univention GmbH
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
try:
	import cPickle as pickle
except ImportError:
	# py3
	import pickle
import copy
from stat import S_IRUSR, S_IWUSR

import listener
from univention.office365.azure_auth import log_a, log_p, AzureAuth
from univention.office365.listener import Office365Listener


listener.configRegistry.load()


name = 'office365-group'
description = 'sync groups to office 365'
if AzureAuth.is_initialized() and listener.configRegistry.is_true("office365/groups/sync", False):
	filter = '(objectClass=posixGroup)'
	log_p("office 365 group listener active")
else:
	filter = '(foo=bar)'
	log_p("office 365 group listener deactivated")
attributes = ["cn", "description", "uniqueMember"]
modrdn = "1"

OFFICE365_OLD_PICKLE = os.path.join("/var/lib/univention-office365", "office365-group_old_dn")

ldap_cred = dict()
attributes_copy = copy.deepcopy(attributes)  # when handler() runs, all kinds of stuff is suddenly in attributes

def load_old(old):
	if os.path.exists(OFFICE365_OLD_PICKLE):
		f = open(OFFICE365_OLD_PICKLE, "r")
		p = pickle.Unpickler(f)
		old = p.load()
		f.close()
		os.unlink(OFFICE365_OLD_PICKLE)
		return old
	else:
		return old


def save_old(old):
	f = open(OFFICE365_OLD_PICKLE, "w+")
	os.chmod(OFFICE365_OLD_PICKLE, S_IRUSR | S_IWUSR)
	p = pickle.Pickler(f)
	p.dump(old)
	p.clear_memo()
	f.close()


def setdata(key, value):
	global ldap_cred
	ldap_cred[key] = value


def initialize():
	if not listener.configRegistry.is_true("office365/groups/sync", False):
		raise RuntimeError("Office 365 App: syncing of groups is deactivated.")

	if not AzureAuth.is_initialized():
		raise RuntimeError("Office 365 App not initialized yet, please run wizard.")


def clean():
	"""
	Remove  univentionOffice365ObjectID and univentionOffice365Data from all
	user objects.
	"""
	log_p("clean() removing Office 365 ObjectID and Data from all groups.")
	Office365Listener.clean_udm_objects("groups/group", listener.configRegistry["ldap/base"], ldap_cred)


def handler(dn, new, old, command):
	log_a("{}.handler() command: {} dn: {}".format(name, command, dn))
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
		log_a("new and not old -> NEW ({})".format(dn))  # DEBUG
		for groupdn in ol.udm_groups_with_azure_users(dn):
			new_group = ol.create_group_from_ldap(groupdn)
			# save Azure objectId in UDM object
			udm_group = ol.get_udm_group(dn)
			udm_group["UniventionOffice365ObjectID"] = new_group["objectId"]
			udm_group.modify()
			log_p("Created group with displayName: {}  ({})".format(
					new_group["displayName"], new_group["objectId"]))
		log_a("done ({})".format(dn))
		return

	#
	# DELETE group
	#
	if old and not new:
		log_a("old and not new -> DELETE ({})".format(dn))  # DEBUG
		if "univentionOffice365ObjectID" in old:
			ol.delete_group(old)
			log_p("Deleted group '{}' ({}).".format(old["cn"][0], old["univentionOffice365ObjectID"][0]))
		return

	#
	# MODIFY group
	#
	if old and new:
		log_a("old and new -> MODIFY ({})".format(dn))  # DEBUG
		if "univentionOffice365ObjectID" in old or ol.udm_groups_with_azure_users(dn):
			azure_group = ol.modify_group(old, new)
			# save Azure objectId in UDM object
			try:
				object_id = azure_group["objectId"]
			except TypeError:
				# None -> group was deleted
				object_id = None
			udm_group = ol.get_udm_group(dn)
			udm_group["UniventionOffice365ObjectID"] = object_id
			udm_group.modify()

			log_p("Modified group '{}' ({}).".format(old["cn"][0], object_id))
		return
