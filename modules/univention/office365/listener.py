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
import re
import json
import base64
import zlib

import univention.admin.uldap
import univention.admin.objects
from univention.office365.azure_auth import log_a, log_e, log_ex, log_p
from univention.office365.azure_handler import AzureHandler, ResourceNotFoundError


class NoAllocatableSubscriptions(Exception):
	def __init__(self, user, *args, **kwargs):
		self.user = user
		super(NoAllocatableSubscriptions, self).__init__(*args, **kwargs)


class Office365Listener(object):
	def __init__(self, listener, name, attrs, ldap_cred, dn):
		"""
		:param listener: listener object or None
		:param name: str, prepend to log messages
		:param attrs: {"listener": [attributes, listener, listens, on], ... }
		:param ldap_cred: {ldapserver: FQDN, binddn: cn=admin,$ldap_base, basedn: $ldap_base, bindpw: s3cr3t} or None
		:param dn of LDAP object to work on
		"""
		self.listener = listener
		self.attrs = attrs
		self.ldap_cred = ldap_cred
		self.lo = None
		self.po = None
		self.groupmod = None
		self.dn = dn

		if self.listener:
			self.ucr = self.listener.configRegistry
		else:
			# allow use of this class outside listener
			from univention.config_registry import ConfigRegistry
			self.ucr = ConfigRegistry()
		self.ucr.load()

		self.ah = AzureHandler(self.ucr, name)

	@property
	def verified_domains(self):
		return map(itemgetter("name"), self.ah.list_verified_domains())

	def create_user(self, new):
		udm_attrs = self._get_sync_values(self.attrs["listener"], new)
		log_a("Office365Listener.create_user() udm_attrs={}".format(udm_attrs))

		attributes = dict()
		for k, v in udm_attrs.items():
			azure_ldap_attribute_name = self.attrs["mapping"][k]
			if azure_ldap_attribute_name in attributes:
				# property exists already, value must be a list
				if not isinstance(attributes[azure_ldap_attribute_name], list):
					attributes[azure_ldap_attribute_name] = [attributes[azure_ldap_attribute_name]]
				# if value is a list extend, else append
				if isinstance(v, list):
					if any([vv in attributes[azure_ldap_attribute_name] for vv in v]):
						# avoid 400: "Request contains a property with duplicate values."
						continue
					list_method = list.extend
				else:
					if v in attributes[azure_ldap_attribute_name]:
						# avoid 400: "Request contains a property with duplicate values."
						continue
					list_method = list.append
				list_method(attributes[azure_ldap_attribute_name], v)
			else:
				attributes[azure_ldap_attribute_name] = v

		# mandatory attributes, not to be overwritten by user
		mandatory_attributes = dict(
			immutableId=base64.encodestring(new["entryUUID"][0]).rstrip(),
			accountEnabled=True,
			passwordProfile=dict(
				password=self.ah.create_random_pw(),
				forceChangePasswordNextLogin=False
			),
			userPrincipalName="{0}@{1}".format(new["uid"][0], self.verified_domains[0]),
			mailNickname=new["uid"][0],
			displayName=attributes.get("displayName", "no name"),
			usageLocation=new["st"][0] if new.get("st") else self.ucr["ssl/country"],  # TODO: use UCRV
		)
		attributes.update(mandatory_attributes)

		self.ah.create_user(attributes)

		user = self.ah.list_users(ofilter="userPrincipalName eq '{}'".format(attributes["userPrincipalName"]))
		if user["value"]:
			new_user = user["value"][0]
		else:
			raise RuntimeError("Office365Listener.create_user() created user '{}' cannot be retrieved.".format(attributes["userPrincipalName"]))

		subscriptions = self.ah.get_office_web_apps_subscriptions()
		if len(subscriptions) < 1:
			msg = "User '{}'/'{}' created in Azure AD, but no allocatable subscriptions found.".format(
				new["uid"][0], new_user["objectId"])
			raise NoAllocatableSubscriptions(new_user, msg)
		elif len(subscriptions) > 1:
			log_e("Office365Listener.create_user() more than one Office 365 subscription found. Currently not"
				"fully supported. Using first one found.")
		sku_id = subscriptions[0]["skuId"]

		log_p("Office365Listener.create_user() using subscription {} for user {}.".format(
			subscriptions[0]["skuId"], new_user["objectId"]))
		self.ah.add_license(new_user["objectId"], subscriptions[0]["skuId"])

		return new_user

	def delete_user(self, old):
		try:
			object_id = old["univentionOffice365ObjectID"][0]
		except KeyError:
			object_id = self.find_aad_user_by_entryUUID(old["entryUUID"][0])
		if not object_id:
			log_e("Office365Listener.delete_user() couldn't find object_id for user '{}', cannot delete.".format(old["uid"][0]))
			return
		try:
			return self.ah.delete_user(object_id)
		except ResourceNotFoundError as exc:
			log_e("Office365Listener.delete_user() user '{}' didn't exist in Azure: {}.".format(old["uid"][0], exc))
			return

	def deactivate_user(self, old):
		if "univentionOffice365ObjectID" in old and old["univentionOffice365ObjectID"][0]:
			object_id = old["univentionOffice365ObjectID"][0]
		else:
			object_id = self.find_aad_user_by_entryUUID(old["entryUUID"][0])
			if not object_id:
				return
		return self.ah.deactivate_user(object_id)

	def get_udm_user(self, userdn):
		lo, po = self._get_ldap_connection()
		univention.admin.modules.update()
		usersmod = univention.admin.modules.get("users/user")
		univention.admin.modules.init(lo, po, usersmod)
		user = usersmod.object(None, lo, po, userdn)
		user.open()
		return user

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
	def clean_udm_objects(cls, module_s, base, ldap_cred):
		"""
		Remove  univentionOffice365ObjectID and univentionOffice365Data from all
		user/group objects, static for listener.clean().
		:param module_s: str: "users/user", "groups/group", etc
		:param base: str: note to start search from
		:param ldap_cred: dict: LDAP credentials collected in listeners set_data()
		"""
		log_p("Office365Listener.clean_udm_objects() cleaning '{}' objects.".format(module_s))
		filter_s = "(|(univentionOffice365ObjectID=*)(univentionOffice365Data=*))"
		udm_objs = cls.find_udm_objects(module_s, filter_s, base, ldap_cred)
		for udm_obj in udm_objs:
			udm_obj.open()
			log_p("Office365Listener.clean_udm_objects() {}...".format(
					udm_obj["username"] if "username" in udm_obj else udm_obj["name"]))
			udm_obj["UniventionOffice365ObjectID"] = None
			if "UniventionOffice365Data" in udm_obj:
				udm_obj["UniventionOffice365Data"] = base64.encodestring(zlib.compress(json.dumps(None))).rstrip()
			udm_obj.modify()
		log_p("Office365Listener.clean_udm_objects() done.")

	def modify_user(self, old, new):
		modifications = self._diff_old_new(self.attrs["listener"], old, new)
		if modifications:
			log_a("Office365Listener.modify_user() modifications={}".format(modifications))

			udm_attrs = self._get_sync_values(modifications, new)

			attributes = dict()
			for k, v in udm_attrs.items():
				attributes[self.attrs["mapping"][k]] = v

			if "st" in modifications:
				udm_user = self.get_udm_user(self.dn)
				attributes["usageLocation"] = udm_user["country"]  # TODO: use UCRV

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
		if "univentionOffice365ObjectID" in user and user["univentionOffice365ObjectID"][0]:
			object_id = user["univentionOffice365ObjectID"][0]
		else:
			object_id = self.find_aad_user_by_entryUUID(user["entryUUID"][0])
			if not object_id:
				return list()
		return self.ah.list_users(objectid=object_id)

	def create_group(self, name, description, group_dn, add_members=True):
		self.ah.create_group(name, description)

		new_group = self.find_aad_group_by_name(name)
		if not new_group:
			raise RuntimeError("Office365Listener.create_group() created group '{}' cannot be retrieved.".format(name))
		if add_members:
			self.add_ldap_members_to_azure_group(group_dn, new_group["objectId"])
		return new_group

	def create_group_from_new(self, new):
		desc = new.get("description", [""])[0] or None
		name = new["cn"][0]
		return self.create_group(name, desc, self.dn)

	def create_group_from_ldap(self, groupdn, add_members=True):
		udm_group = self.get_udm_group(groupdn)
		desc = udm_group.get("description", None)
		name = udm_group["name"]
		return self.create_group(name, desc, groupdn, add_members)

	def delete_group(self, old):
		try:
			return self.ah.delete_group(old["univentionOffice365ObjectID"][0])
		except ResourceNotFoundError as exc:
			log_e("Group '{}' didn't exist in Azure: {}.".format(old["cn"][0], exc))
			return

	def delete_empty_group(self, group_id):
		"""
		Recursively look if a group or any of it parent groups is empty and remove it.
		:param group_id: str: object id of group (and its parents) to check
		:return: bool: if the group was deleted
		"""
		log_a("Office365Listener.delete_empty_group() group_id={}".format(group_id))

		# get IDs of groups this group is a member of before deleting it
		nested_parent_group_ids = self.ah.member_of_groups(group_id, "groups")["value"]

		# check members
		members = self.ah.get_groups_direct_members(group_id)["value"]
		if members:
			member_ids = self.ah.directory_object_urls_to_object_ids(members)
			azure_objs = list()
			for member_id in member_ids:
				try:
					azure_objs.append(self.ah.list_users(objectid=member_id))
				except ResourceNotFoundError:
					# that's OK - it is probably not a user but a group
					try:
						azure_objs.append(self.ah.list_groups(objectid=member_id))
					except ResourceNotFoundError:
						# ignore
						log_e("Office365Listener.delete_empty_group() found unexpected object in group: {}".format(
							member_id))
			if all(azure_obj["mailNickname"].startswith("ZZZ_deleted_") for azure_obj in azure_objs):
				log_p("Office365Listener.delete_empty_group() all members of group {} are deactivated, "
					"deleting it.".format(group_id))
				self.ah.delete_group(group_id)
			else:
				log_a("Office365Listener.delete_empty_group() group has active members, not deleting it.")
				return False
		else:
			log_p("Office365Listener.delete_empty_group() removing empty group {}...".format(group_id))
			self.ah.delete_group(group_id)

		# check parent groups
		for nested_parent_group_id in nested_parent_group_ids:
			self.delete_empty_group(nested_parent_group_id)

		return True

	def modify_group(self, old, new):
		modification_attributes = self._diff_old_new(self.attrs["listener"], old, new)
		log_a("Office365Listener.modify_group() DN={} modification_attributes={}".format(self.dn, modification_attributes))

		if not modification_attributes:
			log_a("Office365Listener.modify_group() no modifications found, ignoring.")
			return dict(objectId=old["univentionOffice365ObjectID"][0])

		try:
			group_id = old["univentionOffice365ObjectID"][0]
		except KeyError:
			# just create a new group
			azure_group = self.create_group_from_new(new)
			group_id = azure_group["objectId"]
			modification_attributes = dict()

		try:
			azure_group = self.ah.list_groups(objectid=group_id)
			if azure_group["mailNickname"].startswith("ZZZ_deleted_"):
				log_p("Office365Listener.modify_group() reactivating azure group '{}'...".format(azure_group["displayName"]))
				name = new["cn"][0]
				attributes = dict(
					description=new.get("description", [""])[0] or None,
					displayName=name,
					mailEnabled=False,
					mailNickname=name.replace(" ", "_-_"),
					securityEnabled=True
				)
				azure_group = self.ah.modify_group(group_id, attributes)
		except ResourceNotFoundError:
			log_e("Office365Listener.modify_group() azure group doesn't exist (anymore), creating it instead.")
			azure_group = self.create_group_from_new(new)
			modification_attributes = dict()
		group_id = azure_group["objectId"]

		if "uniqueMember" in modification_attributes:
			# In uniqueMember users and groups are both listed. There is no
			# secure way to distinguish between them, so lets have UDM do that
			# for us.
			modification_attributes.remove("uniqueMember")
			set_old = set(old.get("uniqueMember", []))
			set_new = set(new.get("uniqueMember", []))
			removed_members = set_old - set_new
			added_members = set_new - set_old
			log_a("Office365Listener.modify_group() DN={} added_members={} removed_members={}".format(self.dn,
				added_members, removed_members))
			udm_group_old = self.get_udm_group(self.dn)

			# add new members to Azure
			users_and_groups_to_add = list()
			for added_member in added_members:
				if added_member in udm_group_old["users"]:
					udm_user = self.get_udm_user(added_member)
					if (bool(int(udm_user.get("UniventionOffice365Enabled", "0"))) and
						udm_user["UniventionOffice365ObjectID"]):
						users_and_groups_to_add.append(udm_user["UniventionOffice365ObjectID"])
				elif added_member in udm_group_old["nestedGroup"]:
					# check if this group or any of its nested groups has azure_users
					for group_with_azure_users in self.udm_groups_with_azure_users(added_member):
						log_a("Found nested group {} wth azure users...".format(group_with_azure_users))
						udm_group = self.get_udm_group(group_with_azure_users)
						if not udm_group.get("UniventionOffice365ObjectID"):
							new_group = self.create_group_from_ldap(group_with_azure_users)
							udm_group["UniventionOffice365ObjectID"] = new_group["objectId"]
							udm_group.modify()
						if group_with_azure_users in udm_group_old["nestedGroup"]:  # only add direct members to group
							users_and_groups_to_add.append(udm_group["UniventionOffice365ObjectID"])
				else:
					raise RuntimeError("Office365Listener.modify_group() '{}' from new[uniqueMember] not in "
						"'nestedGroup' or 'users'.".format(added_member))

			if users_and_groups_to_add:
				self.ah.add_objects_to_azure_group(group_id, users_and_groups_to_add)

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
							azure_group = self.find_aad_group_by_name(object_name)
							if azure_group:
								member_id = azure_group["objectId"]
						if not member_id:
							# not an Azure user or group or already deleted in Azure
							continue

					else:
						log_e("Office365Listener.modify_group() Couldn't figure out object name from DN '{}'.".format(removed_member))
						continue

				self.ah.delete_group_member(group_id=group_id, member_id=member_id)

		# remove group if it became empty
		deleted = self.delete_empty_group(group_id)
		if deleted:
			return None

		# modify other attributes
		modifications = dict([(mod_attr, new[mod_attr]) for mod_attr in modification_attributes])
		if modification_attributes:
			return self.ah.modify_group(object_id=group_id, modifications=modifications)

		return dict(objectId=group_id)  # for listener to store in UDM object

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
			self.ah.add_objects_to_azure_group(object_id, users_and_groups_to_add)

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

	def find_aad_user_by_entryUUID(self, entryUUID):
		user = self.ah.list_users(ofilter="immutableId eq '{}'".format(base64.encodestring(entryUUID).rstrip()))
		if user["value"]:
			return user["value"][0]["objectId"]
		else:
			log_e("Office365Listener._find_aad_user_by_dn() could not find user with dn='{}'.".format(entryUUID))
			return None

	def find_aad_group_by_name(self, name):
		group = self.ah.list_groups(ofilter="displayName eq '{}'".format(name))
		if group["value"]:
			return group["value"][0]
		else:
			log_e("Office365Listener.find_aad_group_by_name() could not find group with name='{}'.".format(name))
			return None

	@staticmethod
	def _anonymize(txt):
		return uuid.uuid4().get_hex()

	def _get_sync_values(self, attrs, user):
		# anonymize > static > sync
		res = dict()
		for attr in attrs:
			if attr not in user or attr == "univentionOffice365Enabled":
				# user has attribute not set | ignore univentionOffice365Enabled
				continue

			if attr in self.attrs["anonymize"]:
				tmp = map(self._anonymize, user[attr])
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
