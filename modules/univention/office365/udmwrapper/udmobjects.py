import base64
import contextlib
import datetime
import json
import zlib
from six.moves import UserDict
from logging import Logger
from typing import List, Mapping, Any, Iterator, Optional, Dict, Set, Tuple, Union
from enum import Enum

from ldap.filter import escape_filter_chars
from univention.ldap_cache.cache import get_cache
from univention.ldap_cache.frontend import users_in_group

from univention.office365.logging2udebug import get_logger
from univention.office365.udm_helper import UDMHelper


class Version(Enum):
	V1 = 1
	V2 = 2
	V3 = 3
	# V4 = 4


"""
A hierarchy of classes that define specializations on a UDM Object.

			  ┌───────────────────┐
			  │                   │
			  │  UDMOfficeObject  │
			  │                   │
			  └────────┬──────────┘
					   │
		 ┌─────────────┴───────────────┐
		 │                             │
┌────────▼────────┐            ┌───────▼──────────┐
│                 │            │                  │
│  UDMOfficeUser  │            │  UDMOfficeGroup  │
│                 │            │                  │
└─────────────────┘            └──────────────────┘

At the leaves of this hierarchical tree of classes are UDMOfficeUser and UDMOfficeGroup 
that implement the necessary methods to obtain and store the necessary information 
from Azure in a LDAP User or Group object.


"""

class UniventionOffice365Data(UserDict):
	"""
	A class that holds the Office365 data for a UDM object.
	The representation of this data have changed in several versions of the connector.
	This class is used to store the data in a uniform way and to provide a consistent
	interface for the different versions.
	"""
	def __init__(self, data):
		# type: (Dict[str, Union[Dict[str,str], str]]) -> None
		super(UniventionOffice365Data, self).__init__(data)

	@classmethod
	def from_ldap(cls, ldap_data):
		# type: (str) -> UniventionOffice365Data
		"""
		Decode ldap UniventionOffice365Data
		Calling code must catch zlib.error and TypeError
		"""
		result = base64.b64decode(ldap_data)
		result = zlib.decompress(result)
		result = json.loads(result.decode("ASCII"))
		return UniventionOffice365Data(result)
		# self.update(json.loads(zlib.decompress(base64.b64decode(ldap_data))))

	def to_ldap_str(self):
		# type: () -> str
		"""
		Encode ldap UniventionOffice365Data
		"""
		result = json.dumps(dict(self)).encode("ASCII")
		result = zlib.compress(result)
		result = base64.b64encode(result).decode("ASCII")
		return result

	def migrate(self):
		# type: () -> None
		if 'objectId' in self and not isinstance(self['objectId'], dict):
			self.update({
				k: v
				for k, v in self.items()
				if isinstance(v, dict)
			})


# TODO: Implement a .get classmethod with the dn as we have in AzureObjects
class UDMOfficeObject(UserDict):
	"""
	Represents an UDM object with Azure data stored in it.
	This is the parent class of UDMOfficeUser and UDMOfficeGroup and implements the common methods for both.
	Self
	Local attributes:
		migrated_to_v3: True if the object has been migrated to v3
		adconnection_aliases: List of AD connection aliases
		current_connection_alias: The current AD connection alias used to connect
		udm_connector: The UDM connector used to connect to the UDM and get the object reference.
		udm_object_reference: The UDM object reference connected to LDAP
	Methods:
		aliases: Return an iterator over the adconnection_aliases
		alias_to_modify: Given another UDMOfficeObject as target, return the aliases that should be modified.
		alias_to_deactivate: Given another UDMOfficeObject as target, return the aliases that should be removed.
		update_azure_data: Update the Azure data of the UDM object.
		update_azure_object_id: Update the Azure object ID of the UDM object.
		update_adconnection_alias: Update the AD connection alias of the UDM object.
		modify_azure_attributes: Modify the Azure attributes of the UDM object with the given data (dict from azure).
		deactivate_azure_attributes: Deactivate the Azure attributes of the UDM object setting it to None.
		create_azure_attributes: Create the Azure attributes of the UDM object with the given data (dict from azure).
		_fields_without_decoding: Return the list of fields that have no decoding specified.
		_fields_without_type_conversion: Return the list of fields that have no type conversion specified.
	"""
	# TODO: Check if adconnection_alias is really mandatory and would exist in v1 and v2 version of the object
	MODULE = None
	# TODO: can adconnection_aliases be directly obtained by this class?

	def __init__(self, ldap_fields, ldap_cred=None, dn='', logger=None):
		# type: (Dict[str, List[bytes]], Optional[Dict[str, Any]], str, Optional[Logger]) -> None
		self.dn = dn
		super(UDMOfficeObject, self).__init__(ldap_fields)
		self.logger = logger or get_logger("office365", "o365")
		# not_migrated_to_v3: on v3 UniventionOffice365Data contains a dict with multiple adconnection_alias and for each of them the data of an azure user.

		# TODO:
		#  split UDMHelper into UDMHelper and UDMOfficeHelper.
		#  If not, current implementation of UDMHelper depends of adconnection_alias which is specific to UDM office objects.
		self.ldap_cred = ldap_cred
		self.udm_connector = UDMHelper(ldap_cred)
		try:
			self.udm_object_reference = self.udm_connector.get_udm_object(self.MODULE, self.dn, attributes=ldap_fields)
			if not ldap_fields:
				self.update(self.udm_object_reference.oldattr)
		except:
			self.logger.error("=" * 50)
			self.logger.error(self.MODULE)
			self.logger.error(self.dn)
			self.logger.error("=" * 50)
			raise
		# self.adconnection_aliases = self.udm_object_reference.get("UniventionOffice365ADConnectionAlias", [])   # type List[str]
		self.current_connection_alias = None

	@property
	def entryUUID(self):
		# type: () -> str
		return self.udm_object_reference.oldattr["entryUUID"][0].decode('UTF-8')

	def __getattr__(self, item):
		# type: (str) -> Any
		return self.__getitem__(item)

	def __getitem__(self, item):
		# type: (str) -> Any
		if item in self.udm_object_reference:
			return self.udm_object_reference[item]
		else:
			udm_item_name = self.udm_object_reference.mapping.unmapName(item)
			if udm_item_name:
				return self.udm_object_reference[udm_item_name]
			elif item in self.udm_object_reference.oldattr:
				return self.udm_object_reference.oldattr[item]
			else:
				raise KeyError("{item} not found in object {dn}".format(item=item, dn=self.dn))

	def __hash__(self):
		# type: () -> int
		return hash(self.dn)

	def __eq__(self, other):
		# type: (UDMOfficeObject) -> bool
		return self.dn == other.dn

	@contextlib.contextmanager
	def set_current_alias(self, alias):
		# type: (str) -> None
		alias_bk, self.current_connection_alias = self.current_connection_alias, alias
		yield
		self.current_connection_alias = alias_bk

	@property
	def adconnection_aliases(self):
		# type: () -> List[str]
		return self.udm_object_reference.get("UniventionOffice365ADConnectionAlias", [])

	@property
	def azure_data(self):
		# type: () -> UniventionOffice365Data
		try:
			return UniventionOffice365Data.from_ldap(self.udm_object_reference["UniventionOffice365Data"]) or {}
		except (zlib.error) :
			return {}

	@property
	def version(self):
		# type: () -> Version
		if self.udm_object_reference.get("UniventionOffice365ObjectID"):
			return Version.V1
		elif self.udm_object_reference.get("UniventionOffice365Data"):
			azure_data = self.azure_data.get(self.current_connection_alias)
			if azure_data:
				if "objectId" in azure_data:
					return Version.V3
				else:
					raise ValueError("Unknow version %r" % azure_data)
			else:
				return Version.V3
		return Version.V3

	def is_version(self, version=Version.V3):
		# type: (Version) -> bool
		return self.version == version

	def aliases(self, aliases=None):
		# type: (set[str]) -> Iterator[str]
		"""
		Generator for the aliases of the user.
		It updates the current_connection_alias if the user while looping over the aliases.
		"""
		aliases = aliases if aliases is not None else self.adconnection_aliases
		for alias_name in aliases:
			self.current_connection_alias = alias_name
			yield alias_name
		self.current_connection_alias = None

	def alias_to_modify(self, other):
		# type: (UDMOfficeObject) -> Iterator[str]
		"""
		Generator
		given another user object, return the alias that should be modified
		The aliases to be modified are the ones that are in the current user object and also in the other user object.
		"""
		return self.aliases(set(self.adconnection_aliases) & set(other.adconnection_aliases))

	def _update_azure_data(self, azure_object_dict):
		# type: (Mapping[str, str]) -> None
		# TODO move out azure_object_dict = {"objectId": azure_object_dict["id"], "userPrincipalName": azure_object_dict["userPrincipalName"]}
		# Create azure data entry for adconnection_alias
		old_azure_data = self.azure_data
		if azure_object_dict:
			new_azure_data = {self.current_connection_alias: azure_object_dict or {}}
			# get the old dict of azure data for all connections
			# update the old dict with the new one
			old_azure_data.update(new_azure_data)
		# else:
		# 	old_azure_data[self.current_connection_alias] =
		# 	old_azure_data.pop(self.current_connection_alias)
		self.udm_object_reference["UniventionOffice365Data"] = UniventionOffice365Data.to_ldap_str(old_azure_data)

	def modify_azure_attributes(self, azure_object_dict):
		# type: (Optional[Mapping]) -> None
		"""
		azure_object_dict: is the dict representing the response of azure to a get object call
		"""
		self._update_azure_data(azure_object_dict)
		self.udm_object_reference.modify()

	def deactivate_azure_attributes(self):
		# type: () -> None
		self.modify_azure_attributes(None)

	def create_azure_attributes(self, azure_object_dict, new_connection_alias=None):
		# type: (Mapping[str, Any], Optional[str]) -> None
		old_current_connection_alias = self.current_connection_alias
		if new_connection_alias:
			self.current_connection_alias = new_connection_alias
		self.modify_azure_attributes(azure_object_dict)
		self.current_connection_alias = old_current_connection_alias

	@property
	def azure_object_id(self):
		# type: () -> Optional[str]
		try:
			if self.is_version(Version.V3):
				azure_data = self.azure_data
				return azure_data[self.current_connection_alias]["objectId"]
			elif self.is_version(Version.V1):  # TODO maybe a migrate script is needed
				return self.udm_object_reference["UniventionOffice365ObjectID"]
		except KeyError:
			return None

	def modified_fields(self, other):
		# type: (UDMOfficeObject) -> List[str]
		"""
		Return the keys of the fields that are different between self and other
		"""
		result = []
		fieldls = list(set(list(self.udm_object_reference.keys())) and set(list(other.udm_object_reference.keys())))  # TODO review if it's an addition or subtraction
		for field in fieldls:
			own_value = getattr(self, field, None)
			other_value = getattr(other, field, None)
			if own_value != other_value:
				result.append(field)
		return result

	def get_diff_aliases(self, other):
		# type: (UDMOfficeObject) -> List[str]
		return list(set(self.adconnection_aliases) - set(other.adconnection_aliases))

	def diff_keys(self, other):
		# type: (UDMOfficeObject) -> Set[str]
		"""
		Return an specific implementation of the difference between self and other.
		The main idea is to set Other as a target and self as a source.
		So the resulting UDMOfficeObject will represent the changes needed to be made to self to make it equal to other.
		If the values of the fields are the same:
			If the values of the fields are lists:
				The resulting UDMOfficeObject will have these fields containing the values of the list that are not equal in other and self.
			If the values of the fields are not lists and are different:
				The resulting UDMOfficeObject will have these fields containing the value of other.

		"""
		assert type(self) == type(other)
		result = {}
		fieldls = other.udm_object_reference.oldattr.keys()
		for field in fieldls:
			own_value = self.udm_object_reference.oldattr.get(field, None)
			other_value = other.udm_object_reference.oldattr.get(field, None)
			# By default, the result is the other value, the change itself.
			if own_value != other_value:
				result[field] = other_value
		return set(result.keys())

	# def __len__(self):
	# 	# type: () -> int
	# 	return len(list(self.keys()))



class UDMOfficeUser(UDMOfficeObject):
	"""
	Represents a user in UDM with Azure data stored in it.
	This is a subclass of UDMOfficeObject and implements the user-specific methods.
	Local attributes:
		MODULE: "users/user" the corresponding UDM module name for this object.
		MANDATORY_FIELDS: the set of fields that must be present in the UDM object.
		DECODINGS: the mapping from LDAP fields names to decoding functions.
		TYPES: the mapping from LDAP fields names to types.
	Methods:
		from_udm: creates a UDMOfficeUser object from a UDM object.
		is_deactivated_locked_or_expired: checks if the user is deactivated, locked or expired. Returns True if so.
		is_expired: checks if the user is expired. Returns True if so.
	"""
	MODULE = "users/user"

	@classmethod
	def from_udm(cls, udm_user, ldap_cred=None):
		# type: (User.user, Optional[Mapping[str,Any]]) -> UDMOfficeUser
		result = cls(udm_user.oldattr, ldap_cred)
		# result.udm_object_reference = udm_user  # TODO ????
		return result

	def is_deactivated_locked_or_expired(self):
		# type: () -> bool
		return bool(int(self.get("disabled"))) or bool(int(self.get("locked"))) or self.is_expired()

	def is_expired(self):
		# type: () -> bool
		try:
			userexpiry = self.udm_object_reference.get("userexpiry")
			return userexpiry is not None and datetime.datetime.strptime(userexpiry, "%Y-%m-%d") < datetime.datetime.now()
		except ValueError:
			self.logger.exception("Bad data in userexpiry: %r", self.userexpiry)
			return True

	def is_enable(self):
		# type: () -> bool
		return bool(int(getattr(self, "UniventionOffice365Enabled", "0")))

	def should_sync(self):
		return not self.is_deactivated_locked_or_expired() and self.is_enable()


class UDMOfficeGroup(UDMOfficeObject):
	"""
	Represents a group in UDM with Azure data stored in it.
	This is a subclass of UDMOfficeObject and implements the group-specific methods.
	Local attributes:
		MODULE: "groups/group" the corresponding UDM module name for this object.
		MANDATORY_FIELDS: the set of fields that must be present in the UDM object.
		DECODINGS: the mapping from LDAP fields names to decoding functions.
		TYPES: the mapping from LDAP fields names to types.
	Methods:
		in_azure: Returns True if the group is in Azure. It uses the UDM Cache to do this.
		is_team: Returns True if the group is a team checking in the UDM Attributes
		owners_dn: Returns the DNs of the owners of the group.
		get_owners: Returns the UDMUsers of the owners of the group.
	"""
	MODULE = "groups/group"

	@classmethod
	def get_other_by_displayName(cls, displayName, ldap_cred):
		# type: (str, Mapping[str,str]) -> Optional[UDMOfficeGroup]
		udm_connector = UDMHelper(ldap_cred)
		udm_objs = udm_connector.find_udm_group_by_name(displayName)
		if udm_objs:
			return UDMOfficeGroup(udm_objs.oldattr, ldap_cred, udm_objs["dn"])

	def modify_azure_attributes(self, azure_group_dict):
		# type: (Optional[Mapping[str, Any]]) -> None
		"""
		"""
		if azure_group_dict is not None:
			self.udm_object_reference["UniventionOffice365ADConnectionAlias"].append(self.current_connection_alias)
		else:
			self.udm_object_reference["UniventionOffice365ADConnectionAlias"] = [x for x in self.adconnection_aliases if x != self.current_connection_alias]
		super(UDMOfficeGroup, self).modify_azure_attributes(azure_group_dict)

	def delete_azure_data(self):
		# type: () -> None
		self.modify_azure_attributes(None)

	def in_azure(self):
		# type: () -> bool
		cache = get_cache()
		univentionOffice365Enabled = cache.get_sub_cache('univentionOffice365Enabled')
		univentionOffice365ADConnectionAlias = cache.get_sub_cache('reverseUniventionOffice365ADConnectionAlias')
		group_users = set(x.lower() for x in users_in_group(self.dn))
		# TODO: Check if adconnection_alias is the current_connection_alias or the list of all connection_aliases
		print(self.current_connection_alias)
		alias_users = set(x.lower() for x in univentionOffice365ADConnectionAlias.get(self.current_connection_alias))
		# the intersection of the two sets is the users in the group AND have an azure account associated
		for user in group_users & alias_users:
			if bool(int(univentionOffice365Enabled.get(user))):
				return True
		return False

	def is_team(self):
		# type: () -> bool
		return bool(int(self.udm_object_reference.get('UniventionMicrosoft365Team', "0")))

	def get_owners_dn(self):
		# type: () -> List[str]
		return self.udm_object_reference.get("UniventionMicrosoft365GroupOwners", [])

	def get_owners(self):
		# type: () -> List[UDMOfficeUser]
		return [UDMOfficeUser({}, self.ldap_cred, dn=owner_dn) for owner_dn in self.get_owners_dn()]

	def get_members(self):
		# type: () -> List[str]
		members = [x.decode("utf-8") for x in self.get("uniqueMember", [])]
		return members

	def get_nested_group(self):
		# type: () -> List[str]
		return getattr(self, "nestedGroup", [])

	def get_users(self):
		# type: () -> List[str]
		return getattr(self, "users", [])

	def get_users_from_ldap(self):
		# type: () -> List[str]
		# get all users for the adconnection (ignoring group membership) and compare
		# with group members to get azure IDs, because it's faster than
		# iterating (and opening!) lots of UDM objects
		all_users_lo = self.udm_connector.get_ldap_o365_users(attributes=['univentionOffice365Data'], adconnection_alias=self.current_connection_alias)
		all_user_dns = set(all_users_lo.keys())
		member_dns = all_user_dns.intersection(set(self.get_users()))

		users_to_add = []
		for dn, attr in all_users_lo.items():
			if dn in member_dns:
				if "univentionOffice365Data" in attr:
					encode_office365_data = attr.get("univentionOffice365Data")
					if len(encode_office365_data) == 1:
						office365_data = UniventionOffice365Data.from_ldap(encode_office365_data[0])
						if office365_data and self.current_connection_alias in office365_data:
							adconnection_data = office365_data[self.current_connection_alias]
							if "objectId" in adconnection_data and "userPrincipalName" in adconnection_data:
								users_to_add.append(adconnection_data["objectId"])
		return users_to_add

	def has_azure_users(self):
		# type: () -> bool
		""""""
		for _ in self.get_nested_groups_with_azure_users():
			return True
		return False

		# for nested_groupdn in self.get_nested_group():
		# 	if self.__class__(ldap_fields={}, ldap_cred=self.ldap_cred, dn=nested_groupdn).has_azure_users():
		# 		return True
		#
		# for userdn in self.get_users():
		# 	udm_user = UDMOfficeUser(ldap_fields={}, ldap_cred=self.ldap_cred, dn=userdn)
		# 	if bool(int(getattr(udm_user, "UniventionOffice365Enabled", "0"))):
		# 		if self.current_connection_alias in udm_user.adconnection_aliases:
		# 			return True
		# 		elif not udm_user.adconnection_aliases and getattr(udm_user, "UniventionOffice365ObjectID", [''])[0]:
		# 			# In the unmigrated phase this is the state of users.
		# 			# This special elif can be removed later iff we have ensured that all customers have actually migrated
		# 			return True
		#
		# return False

	def get_nested_groups_with_azure_users(self):
		# type: () -> Iterator[UDMOfficeGroup]
		""""""
		has_user = False
		for nested_groupdn in self.get_nested_group():
			group = UDMOfficeGroup(ldap_fields={}, ldap_cred=self.ldap_cred, dn=nested_groupdn)
			with group.set_current_alias(self.current_connection_alias):
				for x in group.udm_groups_with_azure_users():
					has_user = True
					yield x

		if not has_user:
			for userdn in self.get_users():
				udm_user = UDMOfficeUser(ldap_fields={}, ldap_cred=self.ldap_cred, dn=userdn)
				if udm_user.is_enable():
					if self.current_connection_alias in udm_user.adconnection_aliases:
						yield self
						break
					elif not udm_user.adconnection_aliases and getattr(udm_user, "UniventionOffice365ObjectID", [''])[0]:
						# TODO In the unmigrated phase this is the state of users.
						# This special elif can be removed later iff we have ensured that all customers have actually migrated
						yield self
						break
		else:
			yield self

	def get_groups_member_of_not_in_azure(self):
		# type: () -> Iterator[UDMOfficeGroup]
		""""""
		for member_of_dn in self.get("memberOf", []):
			group = UDMOfficeGroup({}, ldap_cred=self.ldap_cred, dn=member_of_dn)
			with group.set_current_alias(self.current_connection_alias):
				if not group.azure_object_id:
					yield group
					for x in group.get_groups_member_of_not_in_azure():
						yield x

	def owners_changes(self, target):
		# type: (UDMOfficeGroup) -> Tuple[Set[UDMOfficeUser], Set[UDMOfficeUser]]
		assert type(self) == type(target)
		set_old = set(self.get_owners())
		set_new = set(target.get_owners())
		removed_owners = set_old - set_new
		added_owners = set_new - set_old
		return added_owners, removed_owners

	def added_owners(self, target):
		# type: (UDMOfficeGroup) -> Set[UDMOfficeUser]
		"""
		Given the 'target' reference calculate the owners to be added from self to
		get the same as the target
		"""
		added, _ = self.owners_changes(target)
		return added

	def removed_owners(self, target):
		# type: (UDMOfficeGroup) -> Set[UDMOfficeUser]
		"""
		Given the 'target' reference calculate the owners to be removed from self to
		get the same as the target
		"""
		_, removed = self.owners_changes(target)
		return removed

	def members_changes(self, target):
		# type: (UDMOfficeGroup) -> Tuple[Set[str], Set[str]]
		assert type(self) == type(target)
		set_old = set(self.get_members())
		set_new = set(target.get_members())
		removed_members_dn = set_old - set_new
		added_members_dn = set_new - set_old
		return added_members_dn, removed_members_dn

	def added_members(self, target):
		# type: (UDMOfficeGroup) -> Set[str]
		"""
		Given the 'target' reference calculate the members to be added from self to
		get the same as the target
		"""
		added, _ = self.members_changes(target)
		return added

	def removed_members(self, target):
		# type: (UDMOfficeGroup) -> Set[str]
		"""
		Given the 'target' reference calculate the members to be removed from self to
		get the same as the target
		"""
		_, removed = self.members_changes(target)
		return removed


