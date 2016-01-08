# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module impl
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

from operator import itemgetter
import uuid
import random
import string
import re

import univention.admin.uldap
import univention.admin.objects
from univention.office365.azure_auth import log_a, log_e, log_ex, log_p
from univention.office365.azure_handler import AzureHandler, ResourceNotFoundError


class Office365Listener(object):
	def __init__(self, listener, name, attrs, ldap_cred):
		"""
		:param listener: listener object or None
		:param name: str, prepend to log messages
		:param attrs: {"listener": [attributes, listener, listens, on], ... }
		:param ldap_cred: {ldapserver: FQDN, binddn: cn=admin,$ldap_base, basedn: $ldap_base, bindpw: s3cr3t} or None
		"""
		self.ah = AzureHandler(listener, name)
		self.listener = listener
		self.attrs = attrs
		self.ldap_cred = ldap_cred
		self.lo = None
		self.po = None
		self.groupmod = None

		if self.listener:
			self.ucr = self.listener.configRegistry
		else:
			# allow use of this class outside listener
			from univention.config_registry import ConfigRegistry
			self.ucr = ConfigRegistry()
		self.ucr.load()

	@property
	def verified_domains(self):
		return map(itemgetter("name"), self.ah.list_verified_domains())

	def create_user(self, new):
		udm_attrs = self._get_sync_values(self.attrs["listener"], new)

		attributes = dict()
		for k, v in udm_attrs.items():
			azure_ldap_attribute_name = self.attrs["mapping"][k]
			if azure_ldap_attribute_name in attributes:
				if isinstance(v, list):
					list_method = list.extend
				else:
					list_method = list.append
				if not isinstance(attributes[azure_ldap_attribute_name], list):
					attributes[azure_ldap_attribute_name] = [attributes[azure_ldap_attribute_name]]
				list_method(attributes[azure_ldap_attribute_name], v)
			else:
				attributes[azure_ldap_attribute_name] = v

		# mandatory attributes, not to be overwritten by user
		mandatory_attributes = dict(
			immutableId=new["entryUUID"][0],
			accountEnabled=True,
			passwordProfile=dict(
				password=u"".join(Office365Listener._get_random_pw()),
				forceChangePasswordNextLogin=False
			),
			# TODO: make these anonymizable
			userPrincipalName="{0}@{1}".format(new["uid"][0], self.verified_domains[0]),  # TODO: make the domain choosable
			mailNickname=new["uid"][0],
			displayName=attributes["displayName"] if "displayName" in attributes else "no name"
		)
		attributes.update(mandatory_attributes)

		self.ah.create_user(attributes)

		# TODO: assign a office license!
		# self.ah.add_license(self, user_id, license_id)

		user = self.ah.list_users(ofilter="userPrincipalName eq '{}'".format(attributes["userPrincipalName"]))
		if user["value"]:
			return user["value"][0]
		else:
			raise RuntimeError("Office365Listener.create_user() created user '{}' cannot be retrieved.".format(attributes["userPrincipalName"]))

	def delete_user(self, old):
		try:
			return self.ah.delete_user(old["univentionOffice365ObjectID"][0])
		except ResourceNotFoundError, e:
			log_e("User '{}' didn't exist in Azure: {}.".format(old["uid"][0], e))
			return

	def deactivate_user(self, old):
		return self.ah.deactivate_user(old["univentionOffice365ObjectID"][0])

	def get_udm_user(self, userdn):
		lo, po = self._get_ldap_connection()
		univention.admin.modules.update()
		usersmod = univention.admin.modules.get("users/user")
		univention.admin.modules.init(lo, po, usersmod)
		user = usersmod.object(None, lo, po, userdn)
		user.open()
		return user

	def modify_user(self, old, new):
		modifications = Office365Listener._diff_old_new(self.attrs["listener"], old, new)
		if modifications:
			log_a("Office365Listener.modify_user() modifications={}".format(modifications))

			udm_attrs = self._get_sync_values(modifications, new)

			attributes = dict()
			for k, v in udm_attrs.items():
				attributes[self.attrs["mapping"][k]] = v

			object_id = new["univentionOffice365ObjectID"][0]
			return self.ah.modify_user(object_id=object_id, modifications=attributes)
		else:
			log_a("Office365Listener.modify_user() no modifications - nothing to do.")
			return

	def get_user(self, user):
		"""
		fetch Azure user object
		:param user: listener old or new
		:return: dict
		"""
		object_id = user["univentionOffice365ObjectID"][0]
		if not object_id:
			upn = "{0}@{1}".format(user["uid"][0], self.verified_domains[0]),  # TODO: make the domain choosable
			user = self.ah.list_users(ofilter="userPrincipalName eq '{}'".format(upn))
			if user["value"]:
				object_id = user["value"][0]["objectId"]
		return self.ah.list_users(objectid=object_id)

	def create_group(self, name, description, group_dn, add_members=True):
		# TODO: support anonymization, etc
		self.ah.create_group(name, description)

		group = self.ah.list_groups(ofilter="displayName eq '{}'".format(name))
		if group["value"]:
			new_group = group["value"][0]
			if add_members:
				self.add_ldap_members_to_azure_group(group_dn, new_group["objectId"])
			return new_group
		else:
			raise RuntimeError("Office365Listener.create_group() created group '{}' cannot be retrieved.".format(name))

	def create_group_from_new(self, new):
		desc = new.get("description", [""])[0] or None
		name = new["cn"][0]
		return self.create_group(name, desc, new["entryDN"][0])

	def create_group_from_ldap(self, groupdn, add_members=True):
		udm_group = self.get_udm_group(groupdn)
		desc = udm_group.get("description", None)
		name = udm_group["name"]
		return self.create_group(name, desc, groupdn, add_members)

	def delete_group(self, old):
		try:
			return self.ah.delete_group(old["univentionOffice365ObjectID"][0])
		except ResourceNotFoundError, e:
			log_e("Group '{}' didn't exist in Azure: {}.".format(old["cn"][0], e))
			return

	def modify_group(self, old, new):
		modification_attributes = Office365Listener._diff_old_new(self.attrs["listener"], old, new)
		# TODO: support anonymization, etc
		log_a("Office365Listener.modify_group() DN={} modification_attributes={}".format(
			old["entryDN"], modification_attributes))

		if not modification_attributes:
			log_a("Office365Listener.modify_group() no modifications found, ignoring.")
			return

		if "univentionOffice365ObjectID" not in old:
			# just create a new group
			return self.create_group_from_new(new)

		if "uniqueMember" in modification_attributes:
			# In uniqueMember users and groups are both listed. There is no
			# secure way to distinguish between them, so lets have UDM do that
			# for us.
			modification_attributes.remove("uniqueMember")
			set_old = set(old.get("uniqueMember", []))
			set_new = set(new.get("uniqueMember", []))
			removed_members = set_old - set_new
			added_members = set_new - set_old
			udm_group_old = self.get_udm_group(old["entryDN"][0])

			# add new members to Azure
			users_and_groups_to_add = list()
			new_groups = list()
			for added_member in added_members:
				if added_member in udm_group_old["users"]:
					udm_user = self.get_udm_user(added_member)
					if bool(int(udm_user.get("UniventionOffice365Enabled", "0"))):
						users_and_groups_to_add.append(udm_user["UniventionOffice365ObjectID"])
				elif added_member in udm_group_old["nestedGroup"]:
					# check if this group or any of its nested groups has azure_users
					for group_with_azure_users in self.udm_groups_with_azure_users(added_member):
						udm_group = self.get_udm_group(group_with_azure_users)
						if not udm_group.get("UniventionOffice365ObjectID"):
							new_group = self.create_group_from_ldap(group_with_azure_users, add_members=False)
							new_groups.append((group_with_azure_users, new_group))
							udm_group["UniventionOffice365ObjectID"] = new_group["objectId"]
							udm_group.modify()
						if group_with_azure_users in udm_group_old["nestedGroup"]:  # only add direct members to group
							users_and_groups_to_add.append(udm_group["UniventionOffice365ObjectID"])
				else:
					raise RuntimeError("Office365Listener.modify_group() '{}' from new[uniqueMember] not in 'nestedGroup' or 'users'.".format(added_member))
			if users_and_groups_to_add:
				self.ah.add_objects_to_group(old["univentionOffice365ObjectID"][0], users_and_groups_to_add)

			# add nested groups
			for group_dn, object_id in new_groups:
				self.add_ldap_members_to_azure_group(group_dn, object_id)

			# remove members
			for removed_member in removed_members:
				# try with UDM user
				udm_obj = self.get_udm_user(removed_member)
				member_id = udm_obj.get("UniventionOffice365ObjectID")
				if not member_id:
					# try with UDM group
					udm_obj = self.get_udm_group(removed_member)
					member_id = udm_obj.get("UniventionOffice365ObjectID")
				if not member_id:
					# group may have been deleted or group may not be an Azure group
					# let's try to remove it from Azure anyway
					# get group using name and search
					m = re.match(r"^(?:cn|uid)=(.*?),.*", removed_member)
					if m:
						object_name = m.groups()[0]
						# try with a user
						azure_user = self.ah.list_users(ofilter="userPrincipalName eq '{}'".format(object_name))
						if azure_user["value"]:
							member_id = azure_user["value"][0]["objectId"]
						else:
							# try with a group
							azure_group = self.ah.list_groups(ofilter="displayName eq '{}'".format(object_name))
							if azure_group["value"]:
								member_id = azure_group["value"][0]["objectId"]
						if not member_id:
							# not an Azure user or group or already deleted in Azure
							continue

					else:
						log_e("Office365Listener.modify_group() Couldn't figure out object name from DN '{}'.".format(removed_member))
						continue

				self.ah.delete_group_member(group_id=old["univentionOffice365ObjectID"][0], member_id=member_id)

		# modify other attributes
		modifications = dict([(mod_attr, new[mod_attr]) for mod_attr in modification_attributes])
		if modification_attributes:
			return self.ah.modify_group(object_id=old["univentionOffice365ObjectID"][0], modifications=modifications)

	def add_ldap_members_to_azure_group(self, group_dn, object_id):
		"""
		Recursively look for users and groups to add to the Azure group.

		:param group_dn: DN of UDM group
		:param object_id: Azure object ID of group to add users/groups to
		:return: None
		"""
		log_a("Office365Listener.add_ldap_members_to_azure_group() group_dn={} object_id={}".format(group_dn, object_id))
		udm_target_group = self.get_udm_group(group_dn)
		users_and_groups_to_add = list()

		for userdn in udm_target_group["users"]:
			udm_user = self.get_udm_user(userdn)
			if bool(int(udm_user.get("UniventionOffice365Enabled", "0"))):
				users_and_groups_to_add.append(udm_user["UniventionOffice365ObjectID"])

		# search tree downwards, create groups as we go, add users to them later
		for groupdn in udm_target_group["nestedGroup"]:
			# check if this group or any of its nested groups has azure_users
			for group_with_azure_users_dn in self.udm_groups_with_azure_users(groupdn):
				udm_group = self.get_udm_group(group_with_azure_users_dn)
				if not udm_group.get("UniventionOffice365ObjectID"):
					new_group = self.create_group_from_ldap(group_with_azure_users_dn, add_members=False)
					udm_group["UniventionOffice365ObjectID"] = new_group["objectId"]
					udm_group.modify()
				if group_with_azure_users_dn in udm_target_group["nestedGroup"]:
					users_and_groups_to_add.append(udm_group["UniventionOffice365ObjectID"])

		# add users to groups
		if users_and_groups_to_add:
			self.ah.add_objects_to_group(object_id, users_and_groups_to_add)

		# search tree upwards, create groups as we go, don't add users
		def _groups_up_the_tree(group):
			for member_dn in group["memberOf"]:
				udm_member = self.get_udm_group(member_dn)
				if not udm_member.get("UniventionOffice365ObjectID"):
					new_group = self.create_group_from_ldap(member_dn, add_members=False)
					udm_member["UniventionOffice365ObjectID"] = new_group["objectId"]
					udm_member.modify()
				_groups_up_the_tree(udm_member)

		_groups_up_the_tree(udm_target_group)

	def udm_groups_with_azure_users(self, groupdn):
		"""
		Recursively search for groups with azure users.

		:param groupdn: group to start with
		:return: list of DNs of groups that have at least one user with UniventionOffice365Enabled=1
		"""
		udm_group = self.get_udm_group(groupdn)

		groups = list()
		for nested_groupdn in udm_group.get("nestedGroup", []):
			groups.extend(self.udm_groups_with_azure_users(nested_groupdn))
		for userdn in udm_group.get("users", []):
			udm_user = self.get_udm_user(userdn)
			if bool(int(udm_user.get("UniventionOffice365Enabled", "0"))):
				groups.append(groupdn)
				break
		return groups

	def get_udm_group(self, groupdn):
		lo, po = self._get_ldap_connection()
		if not self.groupmod:
			univention.admin.modules.update()
			self.groupmod = univention.admin.modules.get("groups/group")
			univention.admin.modules.init(lo, po, self.groupmod)
		group = self.groupmod.object(None, lo, po, groupdn)
		group.open()
		return group

	def get_azure_group(self, name):
		group = self.ah.list_groups(ofilter="displayName eq '{}'".format(name))
		if group["value"]:
			return group["value"][0]
		else:
			return None

	@staticmethod
	def _anonymize(txt):
		return uuid.uuid4().get_hex()

	@staticmethod
	def _get_random_pw():
		# have at least one char from each category in password
		# https://msdn.microsoft.com/en-us/library/azure/jj943764.aspx
		pw = list(random.choice(string.lowercase))
		pw.append(random.choice(string.uppercase))
		pw.append(random.choice(string.digits))
		pw.append(random.choice(u"@#$%^&*-_+=[]{}|\:,.?/`~();"))
		pw.extend(random.choice(string.ascii_letters + string.digits + u"@#$%^&*-_+=[]{}|\:,.?/`~();") for _ in range(12))
		random.shuffle(pw)
		return pw

	def _get_sync_values(self, attrs, user):
		# anonymize > static > sync
		res = dict()
		for attr in attrs:
			if attr not in user or attr == "univentionOffice365Enabled":
				# user has attribute not set | ignore univentionOffice365Enabled
				continue

			if attr in self.attrs["anonymize"]:
				tmp = map(Office365Listener._anonymize, user[attr])
			elif attr in self.attrs["static"]:
				tmp = [self.attrs["static"][attr]]
			elif attr in self.attrs["sync"]:
				tmp = user[attr]
			else:
				raise RuntimeError("Attribute to sync '{}' is not configured through UCR.".format(attr))

			if attr in res:
				if isinstance(res[attr], list):
					res[attr].append(tmp)
				else:
					raise RuntimeError(
						"Office365Listener._get_sync_values() res[{}] already exists with type {} and value '{}'.".format(
							attr,
							type(res[attr]),
							res[attr]))
			else:
				if len(tmp) == 1:
					res[attr] = tmp[0]
				else:
					res[attr] = tmp
		return res

	@staticmethod
	def _diff_old_new(attribs, old, new):
		"""
		:param attribs: list of attributes to take into consideration when looking for modifications
		:param old: listener 'old' dict
		:param new: listener 'new' dict
		:return: list of attributes that changed
		"""
		return [attr for attr in attribs
			if attr in new and attr not in old or
			attr in old and attr not in new or
			(attr in old and attr in new and old[attr] != new[attr])
		]

	# allow this class to be used outside listener
	def _get_ldap_connection(self):
		if not self.lo or not self.po:
			if self.ldap_cred:
				self.lo = univention.admin.uldap.access(
					host=self.ldap_cred["ldapserver"],
					base=self.ldap_cred["basedn"],
					binddn=self.ldap_cred["binddn"],
					bindpw=self.ldap_cred["bindpw"])
				self.po = univention.admin.uldap.position(self.ucr["ldap/base"])
			else:
				self.lo, self.po = univention.admin.uldap.getAdminConnection()
		return self.lo, self.po
