# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module to provision accounts in MS Azure
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
import json
import base64
import zlib
import copy
from stat import S_IRUSR, S_IWUSR

import listener
from univention.office365.azure_auth import log_a, log_e, log_ex, log_p, AzureAuth
from univention.office365.listener import Office365Listener, NoAllocatableSubscriptions


listener.configRegistry.load()
attributes_anonymize = list()
attributes_mapping = dict()
attributes_never = list()
attributes_static = dict()
attributes_sync = list()
attributes_multiple_azure2ldap = dict()


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

	attrs = {"univentionOffice365Enabled"}
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
	no_mapping = [a for a in attrs if a not in attributes_mapping.keys() and a != "univentionOffice365Enabled"]
	if no_mapping:
		log_e("No mappings for attributes {} found - ignoring.".format(no_mapping))
		rm_objs_from_list_or_dict(no_mapping, [attrs, attributes_anonymize, attributes_static, attributes_sync])

	if "univentionOffice365ObjectID" in attrs or "UniventionOffice365Data" in attrs:
		log_e("Nice try.")
		rm_objs_from_list_or_dict(["univentionOffice365ObjectID", "univentionOffice365Data"], [attrs, attributes_anonymize, attributes_static, attributes_sync])

	# just for log readability
	attrs.sort()
	attributes_anonymize.sort()
	attributes_never.sort()
	attributes_sync.sort()

	return attrs


name = 'office365-user'
description = 'sync users to office 365'
filter = '(&(objectClass=univentionOffice365)(uid=*))' if AzureAuth.is_initialized() else '(foo=bar)'
attributes = get_listener_attributes()
modrdn = "1"

OFFICE365_OLD_PICKLE = os.path.join("/var/lib/univention-office365", "office365-user_old_dn")

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

log_p("listener observing attributes: {}".format(attributes))
log_p("attributes mapping UCS->AAD: {}".format(attributes_mapping))
log_p("attributes to sync anonymized: {}".format(attributes_anonymize))
log_p("attributes to never sync: {}".format(attributes_never))
log_p("attributes to statically set in AAD: {}".format(attributes_static))
log_p("attributes to sync: {}".format(attributes_sync))
log_p("attributes to sync from multiple sources: {}".format(attributes_multiple_azure2ldap))


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
	if not AzureAuth.is_initialized():
		raise RuntimeError("Office 365 App not initialized yet, please run wizard.")


def clean():
	"""
	Remove  univentionOffice365ObjectID and univentionOffice365Data from all
	user objects.
	"""
	log_p("clean() removing Office 365 ObjectID and Data from all users.")
	Office365Listener.clean_udm_objects("users/user", listener.configRegistry["ldap/base"], ldap_cred)


def handler(dn, new, old, command):
	log_a("{}.handler() command: {} dn: {}".format(name, command, dn))
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
	new_enabled = bool(int(new.get("univentionOffice365Enabled", ["0"])[0]))

	#
	# NEW or REACTIVATED account
	#
	if new_enabled and not old_enabled:
		log_a("new_enabled and not old_enabled -> NEW or REACTIVATED ({})".format(dn))  # DEBUG
		try:
			new_user = ol.create_user(new)
		except NoAllocatableSubscriptions as exc:
			log_e(str(exc))
			new_user = exc.user
		# save/update Azure objectId and object data in UDM object
		udm_user = ol.get_udm_user(dn)
		udm_user["UniventionOffice365ObjectID"] = new_user["objectId"]
		udm_user["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(new_user))).rstrip()
		udm_user.modify()
		log_p("User creation success. userPrincipalName: {} objectId: {} dn: {}".format(
			new_user["userPrincipalName"], new_user["objectId"], dn))
		return

	#
	# DELETE account
	#
	if old and not new:
		log_a("old and not new -> DELETE ({})".format(dn))  # DEBUG
		ol.delete_user(old)
		log_p("Deleted user '{}'.".format(old["uid"][0]))
		return

	#
	# DEACTIVATE account
	#
	if new and not new_enabled:
		log_a("new and not new_enabled -> DEACTIVATE ({})".format(dn))  # DEBUG
		ol.deactivate_user(old)
		# update Azure objectId and object data in UDM object
		udm_user = ol.get_udm_user(dn)
		# Cannot delete UniventionOffice365Data, because it would result in:
		# ldapError: Inappropriate matching: modify/delete: univentionOffice365Data: no equality matching rule
		# Explanation: http://gcolpart.evolix.net/blog21/delete-facsimiletelephonenumber-attribute/
		udm_user["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(None))).rstrip()
		udm_user.modify()
		log_p("Deactivated user '{}'.".format(old["uid"][0]))
		return

	#
	# MODIFY account
	#
	if old_enabled and new_enabled:
		log_a("old_enabled and new_enabled -> MODIFY ({})".format(dn))  # DEBUG
		ol.modify_user(old, new)
		# update Azure object data in UDM object
		udm_user = ol.get_udm_user(dn)
		azure_user = ol.get_user(old)
		udm_user["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(azure_user))).rstrip()
		udm_user.modify()
		log_p("Modified user '{}'.".format(old["uid"][0]))
		return
