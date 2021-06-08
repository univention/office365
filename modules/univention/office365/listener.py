# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module impl
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

from operator import itemgetter
import uuid
import re
import base64
import json
import zlib
from ldap.filter import filter_format

from univention.office365.api.graph import Graph
from univention.office365.azure_handler import AzureHandler, AddLicenseError, ResourceNotFoundError
from univention.office365.azure_auth import AzureAuth, adconnection_alias_ucrv, default_adconnection_alias_ucrv
from univention.office365.logging2udebug import get_logger
from univention.office365.udm_helper import UDMHelper
from univention.office365.subscriptions import SubscriptionProfile

attributes_system = set((
	"krb5KDCFlags",
	"krb5PasswordEnd",
	"krb5ValidEnd",
	"passwordexpiry",
	"sambaAcctFlags",
	"sambaKickoffTime",
	"shadowExpire",
	"shadowLastChange",
	"shadowMax",
	"univentionOffice365Enabled",
	"univentionOffice365ADConnectionAlias",
	"userexpiry",
	"userPassword",
))  # set literals unknown in python 2.6
adconnection_filter_ucrv = 'office365/adconnection/filter'

logger = get_logger("office365", "o365")


def get_adconnection_filter(ucr, adconnection_aliases):
	ucr_value = ucr[adconnection_filter_ucrv] or ''
	aliases = ucr_value.strip().split()
	res = ''
	for alias in aliases:
		if alias not in adconnection_aliases.keys():
			raise Exception('Alias {!r} from UCR {!r} not listed in UCR {!r}. Exiting.'.format(alias, adconnection_filter_ucrv, adconnection_alias_ucrv))
		if not AzureAuth.is_initialized(alias):
			raise Exception('Alias {!r} from UCR {!r} is not initialized. Exiting.'.format(alias, adconnection_filter_ucrv))
		res += filter_format('(univentionOffice365ADConnectionAlias=%s)', (alias,))
	if len(res.split('=')) > 2:
		res = '(|{})'.format(res)
	return res


class NoAllocatableSubscriptions(Exception):
	def __init__(self, user, adconnection_alias=None, *args, **kwargs):
		self.user = user
		self.adconnection_alias = adconnection_alias
		super(NoAllocatableSubscriptions, self).__init__(*args, **kwargs)


class Office365Listener(object):
	def __init__(self, listener, name, attrs, ldap_cred, dn, adconnection_alias=None):
		"""
		:param listener: listener object or None
		:param name: str, prepend to log messages
		:param attrs: {"listener": [attributes, listener, listens, on], ... }
		:param ldap_cred: {ldapserver: FQDN, binddn: cn=admin,$ldap_base, basedn: $ldap_base, bindpw: s3cr3t} or None
		:param dn of LDAP object to work on
		"""
		self.listener = listener
		self.attrs = attrs
		self.udm = UDMHelper(ldap_cred, adconnection_alias)
		# self.ldap_cred = ldap_cred
		self.dn = dn
		self.adconnection_alias = adconnection_alias
		logger.debug('adconnection_alias=%r', adconnection_alias)

		if self.listener:
			self.ucr = self.listener.configRegistry
		else:
			# allow use of this class outside listener
			from univention.config_registry import ConfigRegistry
			self.ucr = ConfigRegistry()
		self.ucr.load()

		self.not_migrated_to_v3 = self.ucr.is_false('office365/migrate/adconnectionalias')

                self.ah = Graph(self.ucr, name, self.adconnection_alias, logger)

	@property
	def verified_domains(self):
		# Use handler.get_verified_domain_from_disk() for user creation.
		return map(itemgetter("name"), self.ah.list_verified_domains())

	def create_user(self, new):
		udm_attrs = self._get_sync_values(self.attrs["listener"], new)
		logger.debug("udm_attrs=%r adconnection_alias=%r", udm_attrs, self.adconnection_alias)

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
		local_part_of_email_address = new["mailPrimaryAddress"][0].rpartition("@")[0]
		mandatory_attributes = dict(
			immutableId=base64.b64encode(new["entryUUID"][0]),
			accountEnabled=True,
			passwordProfile=dict(
				password=self.ah.create_random_pw(),
				forceChangePasswordNextLogin=False
			),
			userPrincipalName="{0}@{1}".format(local_part_of_email_address, self.ah.get_verified_domain_from_disk()),
			mailNickname=local_part_of_email_address,
			displayName=attributes.get("displayName", "no name"),
			usageLocation=self._get_usage_location(new),
		)
		attributes.update(mandatory_attributes)

		self.ah.create_user(attributes)

		user = self.ah.list_users(ofilter="userPrincipalName eq '{}'".format(attributes["userPrincipalName"]))
		if user["value"]:
			new_user = user["value"][0]
		else:
			raise RuntimeError(
				"Office365Listener.create_user() created user {!r} cannot be retrieved ({!r}).".format(
					attributes["userPrincipalName"], self.adconnection_alias)
			)
		try:
			self.assign_subscription(new, new_user)
		except AddLicenseError as exc:
			logger.warn('Could not add license for subscription %r to user %r: %s', exc.user_id, exc.sku_id, exc.message)

		self.ah.invalidate_all_tokens_for_user(new_user["objectId"])
		return new_user

	def _object_id_from_attrs(self, old_or_new):
		"""
		Lookup objectId for adconnection_alias from either univentionOffice365ObjectID (pre v3) or univentionOffice365Data (v3)
		:param old_or_new: list: attributes of user or group object
		:raises: KeyError
		:return: string: object_id
		"""
		if self.not_migrated_to_v3:
			default_adconnection = self.ucr[default_adconnection_alias_ucrv] or "defaultADconnection"
			azure_data = {
				default_adconnection: {
					"objectId": old_or_new["univentionOffice365ObjectID"][0],
				}
			}
		else:
			try:
				azure_data_encoded = old_or_new['univentionOffice365Data'][0]
				try:
					azure_data = self.decode_o365data(azure_data_encoded) or {}
				except (zlib.error, TypeError):
					azure_data = {}
			except (KeyError, IndexError):
				azure_data = {}
		# May throw KeyError:
		azure_connection_data = azure_data[self.adconnection_alias]
		object_id = azure_connection_data["objectId"]
		return object_id

	def _object_id_from_user_attrs_with_fallback_to_entryUUID(self, obj):
		try:
			object_id = self._object_id_from_attrs(obj)
		except KeyError:
			# Fallback to lookup by entryUUID
			object_id = self.find_aad_user_by_entryUUID(obj["entryUUID"][0])
		return object_id

	def _object_id_from_udm_object(self, udm_obj):
		"""
		Lookup objectId for adconnection_alias from either univentionOffice365ObjectID (pre v3) or univentionOffice365Data (v3)
		:param udm_obj: UDM user or group object
		:raises: KeyError
		:return: string: object_id
		"""
		if self.not_migrated_to_v3:
			default_adconnection = self.ucr[default_adconnection_alias_ucrv] or "defaultADconnection"
			azure_data = {
				default_adconnection: {
					"objectId": udm_obj["UniventionOffice365ObjectID"],
				}
			}
		else:
			try:
				azure_data_encoded = udm_obj['UniventionOffice365Data']
				try:
					azure_data = self.decode_o365data(azure_data_encoded) or {}
				except (zlib.error, TypeError):
					azure_data = {}
			except KeyError:
				azure_data = {}
		# May throw KeyError:
		azure_connection_data = azure_data[self.adconnection_alias]
		object_id = azure_connection_data["objectId"]
		if not object_id:
			raise KeyError
		return object_id

	def delete_user(self, old):
		object_id = self._object_id_from_user_attrs_with_fallback_to_entryUUID(old)
		if not object_id:
			logger.error("Couldn't find object_id for user %r (%s), cannot delete.", old["uid"][0], self.adconnection_alias)
			return
		try:
			return self.ah.delete_user(object_id)
		except ResourceNotFoundError as exc:
			logger.error("User %r didn't exist in Azure (%s): %r.", old["uid"][0], self.adconnection_alias, exc)
			return

	def deactivate_user(self, old_or_new):
		object_id = self._object_id_from_user_attrs_with_fallback_to_entryUUID(old_or_new)
		if not object_id:
			return
		return self.ah.deactivate_user(object_id)

	def modify_user(self, old, new):
		modifications = self._diff_old_new(self.attrs["listener"], old, new)
		# If there are properties in azure that get their value from multiple
		# attributes in LDAP, then add all those attributes to the modifications
		# list, or their existing value will be lost, when overwriting them.
		multiples_may_be_none = list()
		for k, v in self.attrs["multiple"].items():
			if any([ldap_attr in modifications for ldap_attr in v]):
				modifications.extend(v)
				multiples_may_be_none.extend(v)
		modifications = list(set(modifications))
		logger.debug("modifications=%r", modifications)
		udm_attrs = self._get_sync_values(modifications, new, modify=True)
		logger.debug("udm_attrs=%r", udm_attrs)
		if udm_attrs:
			attributes = dict()
			for k, v in udm_attrs.items():
				if v is None and k in multiples_may_be_none:
					# property was never set, don't add unnecessary None
					continue
				azure_property_name = self.attrs["mapping"][k]
				if azure_property_name in attributes:
					# must be a list type property, append/extend
					if not isinstance(attributes[azure_property_name], list):
						attributes[azure_property_name] = [attributes[azure_property_name]]
					if isinstance(v, list):
						attributes[azure_property_name].extend(v)
					else:
						attributes[azure_property_name].append(v)
					# no duplicate values
					attributes[azure_property_name] = list(set(attributes[azure_property_name]))
				else:
					attributes[azure_property_name] = v
				# recreate userPrincipalName is mailPrimaryAddress changed
				if k == 'mailPrimaryAddress':
					local_part_of_email_address = v.rpartition("@")[0]
					attributes['userPrincipalName'] = "{0}@{1}".format(
						local_part_of_email_address,
						self.ah.get_verified_domain_from_disk())

			if "usageLocation" in attributes:
				attributes["usageLocation"] = self._get_usage_location(new)

			object_id = self._object_id_from_user_attrs_with_fallback_to_entryUUID(new)
			if not object_id:
				logger.error("Couldn't find object_id for user %r (%s), cannot modify.", new["uid"][0], self.adconnection_alias)
				return

			return self.ah.modify_user(object_id=object_id, modifications=attributes)
		else:
			logger.debug("No modifications - nothing to do.")
			return

	def get_user(self, user):
		"""
		fetch Azure user object
		:param user: listener old or new
		:return: dict
		"""
		object_id = self._object_id_from_user_attrs_with_fallback_to_entryUUID(user)
		if not object_id:
			return list()
		return self.ah.list_users(objectid=object_id)

	def create_groups(self, dn, new):
		if self.udm.udm_groups_with_azure_users(dn):
			new_group = self.create_group_from_new(new)
			# save Azure objectId in UDM object
			udm_group = self.udm.get_udm_group(dn)
			self.set_adconnection_object_id(udm_group, new_group["objectId"])
			logger.info("Created group with displayName: %r (%r) adconnection: %s", new_group["displayName"], new_group["objectId"], self.adconnection_alias)

	def create_group(self, name, description, group_dn, add_members=True):
		self.ah.create_group(name, description)

		new_group = self.find_aad_group_by_name(name)
		if not new_group:
			raise RuntimeError("Office365Listener.create_group() created group {!r} cannot be retrieved ({!r}).".format(name, self.adconnection_alias))
		if add_members:
			self.add_ldap_members_to_azure_group(group_dn, new_group["objectId"])
		return new_group

	def create_group_from_new(self, new):
		desc = new.get("description", [""])[0] or None
		name = new["cn"][0]
		return self.create_group(name, desc, self.dn)

	def create_group_from_ldap(self, groupdn, add_members=True):
		udm_group = self.udm.get_udm_group(groupdn)
		desc = udm_group.get("description", None)
		name = udm_group["name"]
		return self.create_group(name, desc, groupdn, add_members)

	def create_group_from_udm(self, udm_group, add_members=True):
		desc = udm_group.get("description", None)
		name = udm_group["name"]
		return self.create_group(name, desc, udm_group.dn, add_members)

	def delete_group(self, old):
		try:
			object_id = self._object_id_from_attrs(old)
		except KeyError:
			logger.error("Couldn't find object_id for group %r (%s), cannot delete.", old["cn"][0], self.adconnection_alias)
			return
		try:
			azure_group = self.ah.delete_group(object_id)
			logger.info("Deleted group %r from Azure AD '%r'", old["cn"][0], self.adconnection_alias)
			return azure_group
		except ResourceNotFoundError as exc:
			logger.error("Group %r didn't exist in Azure: %r.", old["cn"][0], exc)
			return

	def set_adconnection_object_id(self, udm_group, object_id):
		if self.not_migrated_to_v3:
			udm_group["UniventionOffice365ObjectID"] = object_id
		else:
			azure_data_encoded = udm_group.get("UniventionOffice365Data")
			try:
				azure_data = self.decode_o365data(azure_data_encoded)
				# The account already has an Azure AD connection
			except (zlib.error, TypeError):
				azure_data = {}
			if object_id:
				azure_connection_data = {
					'objectId': object_id
				}
				new_azure_data = {
					self.adconnection_alias: azure_connection_data
				}
				if azure_data:
					azure_data.update(new_azure_data)
					new_azure_data = azure_data
				new_azure_data_encoded = self.encode_o365data(new_azure_data)
				udm_group["UniventionOffice365Data"] = new_azure_data_encoded
				udm_group["UniventionOffice365ADConnectionAlias"].append(self.adconnection_alias)
			else:
				if self.adconnection_alias in azure_data:
					del azure_data[self.adconnection_alias]
					new_azure_data_encoded = self.encode_o365data(azure_data) if azure_data else None
					udm_group["UniventionOffice365Data"] = new_azure_data_encoded
				udm_group["UniventionOffice365ADConnectionAlias"] = [x for x in udm_group["UniventionOffice365ADConnectionAlias"] if x != self.adconnection_alias]
		udm_group.modify()

	def delete_empty_group(self, group_id, udm_group=None):
		"""
		Recursively look if a group or any of it parent groups is empty and remove it.
		:param group_id: str: object id of group (and its parents) to check
		:return: bool: if the group was deleted
		"""
		logger.debug("group_id=%r (%s)", group_id, self.adconnection_alias)

		# get IDs of groups this group is a member of before deleting it
		nested_parent_group_ids = self.ah.member_of_groups(group_id, "groups")["value"]

		# check members
		members = self.ah.get_groups_direct_members(group_id)["value"]
		if members:
			# TODO, find another way to check for active members
			# this for member_id ...
			#          self.ah.list_users
			# is just too expensive,
			# think about it, if we have a group with 100 members and we create another
			# 100 users (members of that group) this creates over 10000 requests

			#member_ids = self.ah.directory_object_urls_to_object_ids(members)
			#azure_objs = list()
			#for member_id in member_ids:
			#	try:
			#		azure_objs.append(self.ah.list_users(objectid=member_id))
			#	except ResourceNotFoundError:
			#		# that's OK - it is probably not a user but a group
			#		try:
			#			azure_objs.append(self.ah.list_groups(objectid=member_id))
			#		except ResourceNotFoundError:
			#			# ignore
			#			logger.error("Office365Listener.delete_empty_group() found unexpected object in group: %r, ignoring.", member_id)
			#if all(azure_obj["mailNickname"].startswith("ZZZ_deleted_") for azure_obj in azure_objs):
			#	logger.info("All members of group %r (%s) are deactivated, deleting it.", group_id, self.adconnection_alias)
			#	self.ah.delete_group(group_id)
			#	if not udm_group:
			#		try:
			#			azure_group = self.ah.list_groups(objectid=group_id)
			#		except ResourceNotFoundError:
			#			# ignore
			#			azure_group = None
			#			logger.error("Office365Listener.delete_empty_group() failed to find own group: %r, ignoring.", group_id)
			#		if azure_group:
			#			udm_group = self.udm.lookup_udm_group(azure_group["displayName"])
			#	if udm_group:  # TODO: lookup group in UDM if not given
			#		self.set_adconnection_object_id(udm_group, None)
			#else:
			logger.debug("Group has active members, not deleting it.")
			return False
		else:
			logger.info("Removing empty group %r (%s)...", group_id, self.adconnection_alias)
			self.ah.delete_group(group_id)
			if not udm_group:
				try:
					azure_group = self.ah.list_groups(objectid=group_id)
				except ResourceNotFoundError:
					# ignore
					azure_group = None
					logger.error("Office365Listener.delete_empty_group() failed to find own group: %r, ignoring.", group_id)
				if azure_group:
					udm_group = self.udm.lookup_udm_group(azure_group["displayName"])
			if udm_group:  # TODO: lookup group in UDM if not given
				self.set_adconnection_object_id(udm_group, None)

		# check parent groups
		for nested_parent_group_id in nested_parent_group_ids:
			self.delete_empty_group(nested_parent_group_id)

		return True

	def modify_group(self, old, new):
		modification_attributes = self._diff_old_new(self.attrs["listener"], old, new)
		logger.debug("dn=%r modification_attributes=%r (%s)", self.dn, modification_attributes, self.adconnection_alias)

		try:
			object_id = self._object_id_from_attrs(old)
		except KeyError:
			object_id = None

		if not modification_attributes:
			logger.debug("No modifications found, ignoring.")
			return dict(objectId=object_id)

		udm_group = self.udm.get_udm_group(self.dn)

		if not object_id:
			# just create a new group
			logger.info("No objectID for group %r found, creating a new azure group...", self.dn)
			azure_group = self.create_group_from_new(new)
			object_id = azure_group["objectId"]
			modification_attributes = dict()
			self.set_adconnection_object_id(udm_group, object_id)

		try:
			azure_group = self.ah.list_groups(objectid=object_id)
			if azure_group["mailNickname"].startswith("ZZZ_deleted_"):
				logger.info("Reactivating azure group %r...", azure_group["displayName"])
				name = new["cn"][0]
				attributes = dict(
					description=new.get("description", [""])[0] or None,
					displayName=name,
					mailEnabled=False,
					mailNickname=name.replace(" ", "_-_"),
					securityEnabled=True
				)
				azure_group = self.ah.modify_group(object_id, attributes)
		except ResourceNotFoundError:
			logger.warn("Office365Listener.modify_group() azure group doesn't exist (anymore), creating it instead.")
			azure_group = self.create_group_from_new(new)
			modification_attributes = dict()
		object_id = azure_group["objectId"]

		if "uniqueMember" in modification_attributes:
			# In uniqueMember users and groups are both listed. There is no
			# secure way to distinguish between them, so lets have UDM do that
			# for us.
			modification_attributes.remove("uniqueMember")
			set_old = set(old.get("uniqueMember", []))
			set_new = set(new.get("uniqueMember", []))
			removed_members = set_old - set_new
			added_members = set_new - set_old
			logger.debug("dn=%r added_members=%r removed_members=%r", self.dn, added_members, removed_members)

			# add new members to Azure
			users_and_groups_to_add = list()
			for added_member in added_members:
				if added_member in udm_group["users"]:
					# it's a user
					udm_user = self.udm.get_udm_user(added_member)
					if int(udm_user.get("UniventionOffice365Enabled", "0")):
						try:
							member_object_id = self._object_id_from_udm_object(udm_user)
							users_and_groups_to_add.append(member_object_id)
						except KeyError:
							pass
				elif added_member in udm_group["nestedGroup"]:
					# it's a group
					# check if this group or any of its nested groups has azure_users
					for group_with_azure_users in self.udm.udm_groups_with_azure_users(added_member):
						logger.debug("Found nested group %r with azure users...", group_with_azure_users)
						udm_group_with_azure_users = self.udm.get_udm_group(group_with_azure_users)
						try:
							member_object_id = self._object_id_from_udm_object(udm_group_with_azure_users)
						except KeyError:
							new_group = self.create_group_from_udm(udm_group_with_azure_users)
							member_object_id = new_group["objectId"]
							self.set_adconnection_object_id(udm_group_with_azure_users, member_object_id)
						if group_with_azure_users in udm_group["nestedGroup"]:  # only add direct members to group
							users_and_groups_to_add.append(member_object_id)
				else:
					raise RuntimeError(
						"Office365Listener.modify_group() {!r} from new[uniqueMember] not in "
						"'nestedGroup' or 'users' ({!r}).".format(added_member, self.adconnection_alias)
					)

			if users_and_groups_to_add:
				self.ah.add_objects_to_azure_group(object_id, users_and_groups_to_add)

			# remove members
			for removed_member in removed_members:
				member_id = None
				# try with UDM user
				udm_obj = self.udm.get_udm_user(removed_member)
				try:
					member_id = self._object_id_from_udm_object(udm_obj)
				except (KeyError, TypeError):
					# try with UDM group
					udm_obj = self.udm.get_udm_group(removed_member)
					try:
						member_id = self._object_id_from_udm_object(udm_obj)
					except (KeyError, TypeError):
						pass
				if not member_id:
					# group may have been deleted or group may not be an Azure group
					# let's try to remove it from Azure anyway
					# get group using name and search
					m = re.match(r"^cn=(.*?),.*", removed_member)
					if m:
						object_name = m.groups()[0]
						# do not try with a user account: it will either have
						# been deleted, in which case it will be removed from
						# all groups by AzureHandler.deactivate_user() or if it
						# existed, we'd have found it already at the top of the
						# for loop with self.get_udm_user(removed_member).

						# try with a group
						azure_group = self.find_aad_group_by_name(object_name)
						if azure_group:
							member_id = azure_group["objectId"]
						else:
							# not an Azure user or group or already deleted in Azure
							logger.warn(
								"Office365Listener.modify_group(), removing members: couldn't figure out object name from dn %r",
								removed_member
							)
							continue
					else:
						logger.warn(
							"Office365Listener.modify_group(), removing members: couldn't figure out object name from dn %r",
							removed_member
						)
						continue

				self.ah.delete_group_member(group_id=object_id, member_id=member_id)

			# remove group if it became empty
			if removed_members and not added_members:
				deleted = self.delete_empty_group(object_id, udm_group)
				if deleted:
					return None

		if 'univentionMicrosoft365TeamAdmins' in modification_attributes:
			logger.warn('trying to add an owner to a team')
			while(1):
				try:
					self.ah.add_group_owner(
						object_id=object_id,
						modification_attributes['univentionMicrosoft365TeamAdmins']
					)
					self.ah.create_team_from_group(object_id=object_id)
					break
				except GraphError:
					sleep(30)
					retry += 30
					if(retry > 150):
						break

		# modify other attributes
		modifications = dict([(mod_attr, new[mod_attr]) for mod_attr in modification_attributes])
		if modification_attributes:
			return self.ah.modify_group(object_id=object_id, modifications=modifications)

		return dict(objectId=object_id)  # for listener to store in UDM object

	def add_ldap_members_to_azure_group(self, group_dn, object_id):
		"""
		Recursively look for users and groups to add to the Azure group.

		:param group_dn: DN of UDM group
		:param object_id: Azure object ID of group to add users/groups to
		:return: None
		"""
		logger.debug("group_dn=%r object_id=%r adconnection_alias=%r", group_dn, object_id, self.adconnection_alias)
		udm_target_group = self.udm.get_udm_group(group_dn)

		# get all users for the adconnection (ignoring group membership) and compare
		# with group members to get azure IDs, because it's faster than
		# iterating (and opening!) lots of UDM objects
		all_users_lo = self.udm.get_lo_o365_users(attributes=['univentionOffice365Data'], adconnection_alias=self.adconnection_alias)
		all_user_dns = set(all_users_lo.keys())
		member_dns = all_user_dns.intersection(set(udm_target_group["users"]))

		def get_object_id(attr):
			try:
				return self._object_id_from_attrs(attr)
			except KeyError:
				# Object is not synchronized to this Azure AD
				pass

		users_and_groups_to_add = [
			oid for oid in [
				get_object_id(attr)
				for dn, attr in all_users_lo.items()
				if dn in member_dns
			]
			if oid is not None
		]

		# search tree downwards, create groups as we go, add users to them later
		for groupdn in udm_target_group["nestedGroup"]:
			# check if this group or any of its nested groups has azure_users
			for group_with_azure_users_dn in self.udm.udm_groups_with_azure_users(groupdn):
				udm_group = self.udm.get_udm_group(group_with_azure_users_dn)
				try:
					member_object_id = self._object_id_from_udm_object(udm_group)
				except KeyError:
					new_group = self.create_group_from_udm(udm_group, add_members=False)
					member_object_id = new_group["objectId"]
					self.set_adconnection_object_id(udm_group, member_object_id)
				if group_with_azure_users_dn in udm_target_group["nestedGroup"]:
					users_and_groups_to_add.append(member_object_id)

		# add users to groups
		if users_and_groups_to_add:
			self.ah.add_objects_to_azure_group(object_id, users_and_groups_to_add)

		# search tree upwards, create groups as we go, don't add users
		def _groups_up_the_tree(group):
			for member_dn in group["memberOf"]:
				udm_member = self.udm.get_udm_group(member_dn)
				try:
					member_object_id = self._object_id_from_udm_object(udm_member)
				except KeyError:
					new_group = self.create_group_from_udm(udm_member, add_members=False)
					member_object_id = new_group["objectId"]
					self.set_adconnection_object_id(udm_member, member_object_id)

				_groups_up_the_tree(udm_member)

		_groups_up_the_tree(udm_target_group)

	def assign_subscription(self, new, azure_user):
		msg_no_allocatable_subscriptions = 'User {}/{} created in Azure AD ({}), but no allocatable subscriptions' \
			' found.'.format(new['uid'][0], azure_user['objectId'], self.adconnection_alias)
		msg_multiple_subscriptions = 'More than one usable Microsoft 365 subscription found.'

		# check subscription availability in azure
		subscriptions_online = self.ah.get_enabled_subscriptions()
		if len(subscriptions_online) < 1:
			raise NoAllocatableSubscriptions(azure_user, msg_no_allocatable_subscriptions, self.adconnection_alias)

		# get SubscriptionProfiles for users groups
		users_group_dns = self.udm.get_udm_user(new['entryDN'][0])['groups']
		users_subscription_profiles = SubscriptionProfile.get_profiles_for_groups(users_group_dns)
		logger.info('SubscriptionProfiles found for %r (%s): %r', new['uid'][0], self.adconnection_alias, users_subscription_profiles)
		if not users_subscription_profiles:
			logger.warn('No SubscriptionProfiles: using all available subscriptions (%s).', self.adconnection_alias)
			if len(subscriptions_online) > 1:
				logger.warn(msg_multiple_subscriptions)
			self.ah.add_license(azure_user['objectId'], subscriptions_online[0]['skuId'])
			return

		# find subscription with free seats
		seats = dict((s["skuPartNumber"], (s["prepaidUnits"]["enabled"], s["consumedUnits"], s['skuId'])) for s in subscriptions_online)
		logger.debug('seats in subscriptions_online: %r', seats)
		subscription_profile_to_use = None
		for subscription_profile in users_subscription_profiles:
			skuPartNumber = subscription_profile.subscription
			if skuPartNumber not in seats:
				logger.warn(
					'Subscription from profile %r (%s) could not be found in the enabled subscriptions in Azure.',
					subscription_profile, self.adconnection_alias)
				continue

			if seats[skuPartNumber][0] > seats[skuPartNumber][1]:
				subscription_profile.skuId = seats[skuPartNumber][2]
				subscription_profile_to_use = subscription_profile
				break

		if not subscription_profile_to_use:
			raise NoAllocatableSubscriptions(azure_user, msg_no_allocatable_subscriptions, self.adconnection_alias)

		logger.info(
			'Using subscription profile %r (skuId: %r).',
			subscription_profile_to_use,
			subscription_profile_to_use.skuId)

		# calculate plan restrictions
		# get all plans of this subscription
		plan_names_to_ids = dict()
		for subscription in subscriptions_online:
			if subscription['skuPartNumber'] == subscription_profile_to_use.subscription:
				for plan in subscription['servicePlans']:
					plan_names_to_ids[plan['servicePlanName']] = plan['servicePlanId']

		if subscription_profile_to_use.whitelisted_plans:
			deactivate_plans = set(plan_names_to_ids.keys()) - set(subscription_profile_to_use.whitelisted_plans)
		else:
			deactivate_plans = set()
		deactivate_plans.update(subscription_profile_to_use.blacklisted_plans)
		logger.info('Deactivating plans %s (%s).' % (deactivate_plans, self.adconnection_alias))
		deactivate_plan_ids = [plan_names_to_ids[plan] for plan in deactivate_plans]
		self.ah.add_license(azure_user['objectId'], subscription_profile_to_use.skuId, deactivate_plan_ids)

	def find_aad_user_by_entryUUID(self, entryUUID):
		user = self.ah.list_users(ofilter="immutableId eq '{}'".format(base64.b64encode(entryUUID)))
		if user["value"]:
			return user["value"][0]["objectId"]
		else:
			logger.error("Could not find user with entryUUID=%r (%s).", entryUUID, self.adconnection_alias)
			return None

	def find_aad_group_by_name(self, name):
		group = self.ah.list_groups(ofilter="displayName eq '{}'".format(name))
		if group["value"]:
			return group["value"][0]
		else:
			logger.warn("Could not find group with name=%r (%s), ignore this if it is a user.", name, self.adconnection_alias)
			return None

	@staticmethod
	def _anonymize(txt):
		return uuid.uuid4().get_hex()

	def _get_sync_values(self, attrs, user, modify=False):
		# anonymize > static > sync
		res = dict()
		for attr in attrs:
			if attr in attributes_system:
				# filter out univentionOffice365Enabled and account deactivation/locking attributes
				continue
			elif attr not in user and not modify:
				# only set empty values to unset properties when modifying
				continue
			elif attr in self.attrs["anonymize"]:
				tmp = map(self._anonymize, user[attr])
			elif attr in self.attrs["static"]:
				tmp = [self.attrs["static"][attr]]
			elif attr in self.attrs["sync"]:
				tmp = user.get(attr)  # Azure does not like empty strings - it wants None!
			else:
				raise RuntimeError("Attribute to sync {!r} is not configured through UCR.".format(attr))

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
				if tmp and len(tmp) == 1:
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
		return [
			attr for attr in attribs
			if attr in new and attr not in old or
			attr in old and attr not in new or
			(attr in old and attr in new and old[attr] != new[attr])
		]

	def _get_usage_location(self, user):
		if user.get("st"):
			res = user["st"][0]
		elif self.ucr.get("office365/attributes/usageLocation"):
			res = self.ucr["office365/attributes/usageLocation"]
		else:
			res = self.ucr["ssl/country"]
		if not res or len(res) != 2:
			raise RuntimeError("Invalid usageLocation '{}' - user cannot be created.".format(res))
		return res

	@classmethod
	def decode_o365data(cls, data):
		"""
		Decode ldap UniventionOffice365Data
		Calling code must catch zlib.error and TypeError
		"""
		return json.loads(zlib.decompress(base64.b64decode(data)))

	@classmethod
	def encode_o365data(cls, data):
		"""
		Encode ldap UniventionOffice365Data
		"""
		return base64.b64encode(zlib.compress(json.dumps(data)))
