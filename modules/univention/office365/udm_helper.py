#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle UDM calls
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

import json
import base64
import zlib
import univention.admin.uldap
import univention.admin.objects
from univention.config_registry import ConfigRegistry
from univention.office365.logging2udebug import get_logger


logger = get_logger("office365", "o365")


class UDMHelper(object):
	"""
	UDM functions collection
	"""
	ldap_cred = None
	lo = None
	po = None
	groupmod = None
	usersmod = None

	def __init__(self, ldap_cred):
		UDMHelper.ldap_cred = ldap_cred

	@classmethod
	def clean_udm_objects(cls, module_s, base, ldap_cred):
		"""
		Remove  univentionOffice365ObjectID and univentionOffice365Data from all
		user/group objects, static for listener.clean().
		:param module_s: str: "users/user", "groups/group", etc
		:param base: str: note to start search from
		:param ldap_cred: dict: LDAP credentials collected in listeners set_data()
		"""
		logger.info("Cleaning %r objects....", module_s)
		filter_s = "(|(univentionOffice365ObjectID=*)(univentionOffice365Data=*))"
		udm_objs = cls.find_udm_objects(module_s, filter_s, base, ldap_cred)
		for udm_obj in udm_objs:
			udm_obj.open()
			logger.info("%r...", udm_obj["username"] if "username" in udm_obj else udm_obj["name"])
			udm_obj["UniventionOffice365ObjectID"] = None
			if "UniventionOffice365Data" in udm_obj:
				udm_obj["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(None))).rstrip()
			udm_obj.modify()
		logger.info("Cleaning done.")

	@staticmethod
	def find_udm_objects(module_s, filter_s, base, ldap_cred):
		"""
		search LDAP for UDM objects, static for listener.clean()
		:param module_s: str: "users/user", "groups/group", etc
		:param filter_s: str: LDAP filter string
		:param base: str: note to start search from
		:param ldap_cred: dict: LDAP credentials collected in listeners set_data()
		:return: list of (not yet opened) UDM objects
		"""
		lo = univention.admin.uldap.access(
			host=ldap_cred["ldapserver"],
			base=ldap_cred["basedn"],
			binddn=ldap_cred["binddn"],
			bindpw=ldap_cred["bindpw"])
		po = univention.admin.uldap.position(base)
		univention.admin.modules.update()
		module = univention.admin.modules.get(module_s)
		univention.admin.modules.init(lo, po, module)
		config = univention.admin.config.config()
		return module.lookup(config, lo, filter_s=filter_s, base=base)

	@classmethod
	def get_udm_group(cls, groupdn):
		lo, po = cls._get_ldap_connection()
		if not cls.groupmod:
			univention.admin.modules.update()
			cls.groupmod = univention.admin.modules.get("groups/group")
			univention.admin.modules.init(lo, po, cls.groupmod)
		group = cls.groupmod.object(None, lo, po, groupdn)
		group.open()
		return group

	@classmethod
	def get_udm_user(cls, userdn, attributes=None):
		lo, po = cls._get_ldap_connection()
		if not cls.usersmod:
			univention.admin.modules.update()
			cls.usersmod = univention.admin.modules.get("users/user")
			univention.admin.modules.init(lo, po, cls.usersmod)
		user = cls.usersmod.object(None, lo, po, userdn, attributes=attributes)
		user.open()
		return user

	@classmethod
	def udm_groups_with_azure_users(cls, groupdn):
		"""
		Recursively search for groups with azure users.

		:param groupdn: group to start with
		:return: list of DNs of groups that have at least one user with UniventionOffice365Enabled=1
		"""
		udm_group = cls.get_udm_group(groupdn)

		groups = list()
		for nested_groupdn in udm_group.get("nestedGroup", []):
			groups.extend(cls.udm_groups_with_azure_users(nested_groupdn))
		for userdn in udm_group.get("users", []):
			udm_user = cls.get_udm_user(userdn)
			if bool(int(udm_user.get("UniventionOffice365Enabled", "0"))):
				groups.append(groupdn)
				break
		return groups

	@classmethod
	def _get_ldap_connection(cls):
		if not cls.lo or not cls.po:
			if cls.ldap_cred:
				cls.lo = univention.admin.uldap.access(
					host=cls.ldap_cred["ldapserver"],
					base=cls.ldap_cred["basedn"],
					binddn=cls.ldap_cred["binddn"],
					bindpw=cls.ldap_cred["bindpw"])
				ucr = ConfigRegistry()
				ucr.load()
				cls.po = univention.admin.uldap.position(ucr["ldap/base"])
			else:
				cls.lo, cls.po = univention.admin.uldap.getAdminConnection()
		return cls.lo, cls.po
