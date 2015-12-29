# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module to provision accounts in MS Azure
#
# Copyright 2015 Univention GmbH
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
import cPickle
import json
import base64
import zlib

import listener
from univention.admin.uexceptions import noObject
from univention.office365.azure_auth import log_a, log_e, log_ex, log_p
from univention.office365.listener import Office365Listener


listener.configRegistry.load()
attributes_anonymize = list()
attributes_mapping = dict()
attributes_never = list()
attributes_static = dict()
attributes_sync = list()


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

	attrs = ["univentionOffice365Enabled"]
	for k, v in listener.configRegistry.items():
		if k == "office365/attributes/anonymize":
			attributes_anonymize = [x.strip() for x in v.split(",") if x.strip()]
			attrs.extend(attributes_anonymize)
		elif k.startswith("office365/attributes/mapping/"):
			at = k.split("/")[-1]
			attributes_mapping[at] = v.strip()
		elif k == "office365/attributes/never":
			attributes_never = [x.strip() for x in v.split(",") if x.strip()]
		elif k.startswith("office365/attributes/static/"):
			at = k.split("/")[-1]
			attributes_static[at] = v.strip()
			attrs.append(at)
		elif k == "office365/attributes/sync":
			attributes_sync = [x.strip() for x in v.split(",") if x.strip()]
			attrs.extend(attributes_sync)
		else:
			pass

	# never > anonymize > static > sync
	rm_objs_from_list_or_dict(attributes_never, [attrs, attributes_anonymize, attributes_static, attributes_sync])
	rm_objs_from_list_or_dict(attributes_anonymize, [attributes_static, attributes_sync])
	rm_objs_from_list_or_dict(attributes_static, [attributes_sync])

	# sanity check
	no_mapping = [a for a in attrs if a not in attributes_mapping.keys() and a != "univentionOffice365Enabled"]
	if no_mapping:
		log_e("No mappings for attributes {} found - ignoring.".format(no_mapping))
		rm_objs_from_list_or_dict(no_mapping, [attrs, attributes_anonymize, attributes_static, attributes_sync])

	if "univentionOffice365ObjectID" in attrs or "UniventionOffice365Data" in attrs:
		log_e("Nice try.")
		rm_objs_from_list_or_dict(["univentionOffice365ObjectID", "univentionOffice365Data"], [attrs, attributes_anonymize, attributes_static, attributes_sync])

	return attrs


name = 'office365'
description = 'manage office 365 user'
filter = '(&(objectClass=univentionOffice365)(uid=*))'
attributes = get_listener_attributes()
modrdn = "1"

OFFICE365_OLD_PICKLE = os.path.join("/var/lib/univention-office365", "office365_old_dn")

_attrs = dict(
	anonymize=attributes_anonymize,
	listener=attributes,
	mapping=attributes_mapping,
	never=attributes_never,
	static=attributes_static,
	sync=attributes_sync
)

ldap_cred = dict()

log_p("listener observing attributes: {}".format(attributes))
log_p("attributes mapping UCS->AAD: {}".format(attributes_mapping))
log_p("attributes to sync anonymized: {}".format(attributes_anonymize))
log_p("attributes to never sync: {}".format(attributes_never))
log_p("attributes to statically set in AAD: {}".format(attributes_static))
log_p("attributes to sync: {}".format(attributes_sync))


def load_old(old):
	if os.path.exists(OFFICE365_OLD_PICKLE):
		f = open(OFFICE365_OLD_PICKLE, "r")
		p = cPickle.Unpickler(f)
		old = p.load()
		f.close()
		os.unlink(OFFICE365_OLD_PICKLE)
		return old
	else:
		return old


def save_old(old):
	f = open(OFFICE365_OLD_PICKLE, "w+")
	os.chmod(OFFICE365_OLD_PICKLE, 0600)
	p = cPickle.Pickler(f)
	p.dump(old)
	p.clear_memo()
	f.close()


def setdata(key, value):
	global ldap_cred
	ldap_cred[key] = value


def handler(dn, new, old, command):
	log_a("command: {}".format(command))
	if command == 'r':
		save_old(old)
		return
	elif command == 'a':
		old = load_old(old)

	ol = Office365Listener(listener, name, _attrs)
	old_enabled = bool(int(old.get("univentionOffice365Enabled", ["0"])[0]))  # "" when disabled, "1" when enabled
	new_enabled = bool(int(new.get("univentionOffice365Enabled", ["0"])[0]))

	# log_a("old: {}".format(old))
	# log_a("new: {}".format(new))
	# log_p("old_enabled: {}".format(old_enabled))
	# log_p("new_enabled: {}".format(new_enabled))

	#
	# NEW account
	#
	if new_enabled and not old_enabled:
		log_p("new_enabled and not old_enabled -> NEW")
		new_user = ol.create_user(new)
		udm_user = ol.get_udm_user(ldap_cred, dn)
		udm_user["UniventionOffice365ObjectID"] = new_user["objectId"]
		# fix Bug #40348 first
		# udm_user["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(new_user)))  # TODO: just a test, should be more specific
		udm_user.modify()
		log_p("User creation success. userPrincipalName: {} objectId: {}".format(
				new_user["userPrincipalName"], new_user["objectId"]))
		return

	#
	# DELETE account
	#
	if not new_enabled:
		log_p("not new_enabled -> DELETE")
		ol.delete_user(old)
		try:
			udm_user = ol.get_udm_user(ldap_cred, dn)
			udm_user["UniventionOffice365ObjectID"] = "deactivated"
			# fix Bug #40348 first
			# udm_user["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(None)))
			udm_user.modify()
		except noObject:
			# user was deleted (not just deactivated)
			pass
		log_p("Deleted user '{}'.".format(old["univentionOffice365ObjectID"][0]))
		return

	#
	# MODIFY account
	#
	if old_enabled and new_enabled:
		log_p("old_enabled and new_enabled -> MODIFY")
		ol.modify_user(old, new)
		return
