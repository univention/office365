#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle UDM calls
#
# Copyright 2016-2021 Univention GmbH
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

from ldap.filter import escape_filter_chars, filter_format
from typing import Mapping, Any, Dict, List, Optional


from univention import admin
from univention.config_registry import ConfigRegistry
from univention.office365.logging2udebug import get_logger
from univention.office365.ucr_helper import UCRHelper

logger = get_logger("office365", "o365")


class UDMHelper(object):
	"""
	UDM methods collection specific for the use with office365
	"""
	ldap_cred = None

	def __init__(self, ldap_cred=None):
		self.lo = None
		self.po = None
		self.modules = {}
		self._get_ldap_connection()
		if ldap_cred:
			self.ldap_cred = ldap_cred
			UDMHelper.ldap_cred = ldap_cred

	# LDAP

	def _get_ldap_connection(self):
		if not self.lo or not self.po:
			if self.ldap_cred:
				# {'host': 'ucs-8358.test-idelgado-com.intranet',
				# 'base': 'dc=test-idelgado-com,dc=intranet',
				# 'binddn': 'cn=admin,dc=test-idelgado-com,dc=intranet',
				# 'bindpw': 'kKXv2TJZ6aeuNKKUUbi1'}
				self.lo = admin.uldap.access(
					host=self.ldap_cred["host"],
					base=self.ldap_cred["base"],
					binddn=self.ldap_cred["binddn"],
					bindpw=self.ldap_cred["bindpw"])
				# TODO: Move to UCRHelper?
				ucr = ConfigRegistry()
				ucr.load()
				self.po = admin.uldap.position(ucr["ldap/base"])
			else:
				self.lo, self.po = admin.uldap.getAdminConnection()
		return self.lo, self.po

	def _get_ldap_o365_objects(self, filter_s, attributes):
		"""
		Get all LDAP group/user objects (not UDM groups/users) that are enabled for office 365 sync.

		:param filter_s: str: LDAP filter
		:param attributes: list: get only those attributes
		:return: dict: dn(str) -> attributes(dict)
		"""
		lo, po = self._get_ldap_connection()
		logger.debug('filter_s=%r', filter_s)
		return dict(lo.search(filter_s, attr=attributes))

	def get_ldap_o365_users(self, attributes=None, adconnection_alias=None, enabled='1', additional_filter=''):
		# type: (Optional[List[str]], Optional[str], str, str) -> Dict[str, Any]
		"""
		Get all LDAP user objects (not UDM users) that are enabled for office 365 sync.

		:param attributes: list: get only those attributes

		:param enabled: str: if the user must be enabled for office 365 use: '0': not, '1': yes, '': both
		:param additional_filter: str: will be appended to the AND clause

		:param adconnection_alias: str: get only those users for this adconnection
		:param enabled: str: if the user must be enabled for office 365 use: '0': not, '1': yes, '': both
		:param additional_filter: str: will be appended to the AND clause
		:return: dict: dn(str) -> attributes(dict)
		"""
		if enabled == '':
			enabled_filter = ''
		elif enabled in ('0', '1'):
			enabled_filter = '(univentionOffice365Enabled={})'.format(enabled)
		else:
			raise ValueError("Argument 'enabled' must have value '', '0' or '1'.")
		if adconnection_alias:
			adconnection_filter = filter_format('(univentionOffice365ADConnectionAlias=%s)', (adconnection_alias,))
		elif additional_filter != '(!(univentionOffice365ADConnectionAlias=*))':
			adconnection_filter = '(univentionOffice365ADConnectionAlias=*)'
		else:
			adconnection_filter = ''

		filter_s = '(&(objectClass=posixAccount)(objectClass=univentionOffice365)(uid=*){}{}{})'.format(adconnection_filter, enabled_filter, additional_filter)
		logger.debug('filter_s=%r', filter_s)
		return self._get_ldap_o365_objects(filter_s, attributes)


	def get_ldap_o365_groups(self, attributes=None, adconnection_alias=None, additional_filter=''):
		# type: (Optional[List[str]], Optional[str], str) -> Dict[str, Any]
		"""
		Get all LDAP user objects (not UDM users) that are enabled for office 365 sync.

		:param attributes: list: get only those attributes
		:param adconnection_alias: str: get only those users for this adconnection
		:param additional_filter: str: will be appended to the AND clause
		:return: dict: dn(str) -> attributes(dict)
		"""
		if adconnection_alias:
			adconnection_filter = filter_format('(univentionOffice365ADConnectionAlias=%s)', (adconnection_alias,))
		elif additional_filter != '(!(univentionOffice365ADConnectionAlias=*))':
			adconnection_filter = '(univentionOffice365ADConnectionAlias=*)'
		else:
			adconnection_filter = ''
		filter_s = '(&(objectClass=posixGroup)(objectClass=univentionOffice365)(cn=*){}{})'.format(adconnection_filter, additional_filter)
		return self._get_ldap_o365_objects(filter_s, attributes)

	def _get_module(self, module_name):
		# type: (str) -> Any
		if self.lo is None or self.po is None:
			self._get_ldap_connection()
		try:
			mod = self.modules[module_name]
		except KeyError:
			admin.modules.update()
			mod = admin.modules.get(module_name)
			admin.modules.init(self.lo, self.po, mod)
			self.modules[module_name] = mod
		return mod

	def get_udm_object(self, module_name, dn, attributes=None):
		# type: (str, str, Optional[Dict[str, Any]]) -> object
		assert self.lo is not None, "No LDAP connection have been established"
		mod = self._get_module(module_name)
		obj = mod.object(None, self.lo, self.po, dn, attributes=attributes)
		obj.open()
		return obj

	def get_udm_group(self, groupdn, attributes=None):
		return self.get_udm_object("groups/group", groupdn, attributes)

	def get_udm_user(self, userdn, attributes=None):
		# type: (str, Optional[Dict[str, Any]]) -> Any
		return self.get_udm_object("users/user", userdn, attributes)

	def _find_udm_objects(self, module_s, filter_s, base):
		# type: (str, str, str) -> List[Any]
		"""
		search LDAP for UDM objects, static for listener.clean()

		:param module_s: str: "users/user", "groups/group", etc
		:param filter_s: str: LDAP filter string
		:param base: str: node to start search from
		:param ldap_cred: dict: LDAP credentials collected in listeners set_data()
		:return: list of (not yet opened) UDM objects
		"""
		module = self._get_module(module_s)
		# TODO: check if the first parameter is needed (Config, from univention.admin.config)
		return module.lookup(None, self.lo, filter_s=filter_s, base=base)

	def find_udm_group_by_name(self, name):
		# type: (str) -> Any
		udm_groups = self._find_udm_objects("groups/group", filter_format('(cn=%s)', (name,)), None)
		if len(udm_groups) > 0:
			if len(udm_groups) > 1:
				logger.warn('Found more than one group with name %r', name)
			return udm_groups[0].open()

	def clean_o365_data_from_objects(self, module_s, base, adconnection_filter=''):
		# type: (str, str, str) -> None
		"""
		Remove  univentionOffice365Data from all
		user/group objects, static for listener.clean().

		:param module_s: str: "users/user", "groups/group", etc
		:param base: str: node to start search from
		:param adconnection_filter: str: optional LDAP filter to remove data only
		from matching LDAP objects
		"""
		filter_s = filter_format("(&(objectClass=univentionOffice365)(univentionOffice365Data=*)%s)", (adconnection_filter,))
		logger.info("Cleaning %r objects with filter=%r....", module_s, filter_s)
		udm_objs = self._find_udm_objects(module_s, filter_s, base)
		for udm_obj in udm_objs:
			udm_obj.open()
			logger.info("%r...", udm_obj["username"] if "username" in udm_obj else udm_obj["name"])
			if "UniventionOffice365Data" in udm_obj:
				udm_obj["UniventionOffice365Data"] = None
			udm_obj.modify()
		logger.info("Cleaning done.")

	def clean_o365_data_from_groups(self, base, adconnection_filter=''):
		# type: (str, str) -> None
		"""
		Convenience method to clean univentionOffice365Data from groups
		"""
		self.clean_o365_data_from_objects("groups/group",  base, adconnection_filter)

	def clean_o365_data_from_users(self, base, adconnection_filter=''):
		# type: (str, str) -> None
		"""
		Convenience method to clean univentionOffice365Data from users
		"""
		self.clean_o365_data_from_objects("users/user", base, adconnection_filter)

	# AZURE GROUPS

	def udm_groups_with_users_in_adconnection(self, groupdn, adconnection_alias):
		# type: (str, str) -> List[str]
		"""
		Recursively search for groups with azure users.

		:param groupdn: group to start with
		:return: list of DNs of groups that have at least one user that is enabled for self.adconnection_alias (and has UniventionOffice365Enabled=1)
		"""
		udm_group = self.get_udm_group(groupdn)

		groups = list()
		for nested_groupdn in udm_group.get("nestedGroup", []):
			groups.extend(self.udm_groups_with_users_in_adconnection(nested_groupdn))
		for userdn in udm_group.get("users", []):
			udm_user = self.get_udm_user(userdn)
			if bool(int(udm_user.get("UniventionOffice365Enabled", "0"))):
				if adconnection_alias in udm_user.get("UniventionOffice365ADConnectionAlias", []):
					groups.append(groupdn)
					break
		return groups


	# PROFILES

	def list_udm_office_profiles(self, filter_s=''):
		# type: (str) -> List[Any]
		assert self.lo is not None
		mod = self._get_module('office365/profile')
		return mod.lookup(None, self.lo, filter_s)

	def get_udm_office_profile(self, profile_dn, attributes=None):
		# type: (str, Dict[str, Any]) -> Any
		return self.get_udm_object("office365/profile", profile_dn, attributes)

	# AD Connections

	def create_udm_adconnection(self, alias, description=""):
		# type: (str, str) -> str
		mod = self._get_module("office365/ad-connection")
		# TODO: Move to UCRHelper? parameter?
		ucr = ConfigRegistry()
		ucr.load()
		po = admin.uldap.position("cn=ad-connections,cn=office365,%s" % ucr["ldap/base"])
		adconn = mod.object(co=None, lo=self.lo, position=po)
		adconn.open()
		adconn['name'] = alias
		adconn['description'] = description
		dn = adconn.create()
		return dn

	def remove_udm_adconnection(self, alias):
		# type: (str) -> Union[bool, str]
		mod = self._get_module("office365/ad-connection")
		udm_objs = mod.lookup(None, self.lo, filter_s="cn=%s" % escape_filter_chars(alias))
		if len(udm_objs) == 1:
			udm_objs[0].remove()
			return udm_objs[0].dn
		else:
			return False

	# TODO: NOT SURE IT MUST BE HERE, Filter is for the listener, ucr only must give the needed values
	def get_adconnection_filter_string(self):
		# type: () -> Dict[str, Any]
		res = ""
		adconnection_aliases = self.get_adconnection_aliases()
		for alias in UCRHelper.get_adconnection_filtered_in():
			# TODO: move the check out of this class
			if alias not in adconnection_aliases:
				raise Exception('Alias {!r} from UCR {!r} not listed in UCR {!r}. Exiting.'.format(alias, UCRHelper.adconnection_filter_ucrv, UCRHelper.adconnection_alias_ucrv))
			elif adconnection_aliases[alias] not in ["uninitialized", ""]:
				raise Exception('Alias {!r} from UCR {!r} is not initialized. Exiting.'.format(alias, UCRHelper.adconnection_filter_ucrv))
			res += filter_format('(univentionOffice365ADConnectionAlias=%s)', (alias,))
		if len(res.split('=')) > 2:
			res = '(|{})'.format(res)
		return res
