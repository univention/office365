# -*- coding: utf-8 -*-
import uuid
from abc import abstractmethod
from six.moves import UserDict
from collections import defaultdict
from logging import Logger
from typing import List, Mapping, Dict, Set, Any, Optional
import abc
import six
import univention.admin

from ldap.filter import filter_format
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError, AddLicenseError
from univention.office365.microsoft.exceptions.exceptions import NoAllocatableSubscriptions, GraphRessourceNotFroundError
from univention.office365.connector import utils
from univention.office365.microsoft.objects.azureobjects import UserAzure, AzureObject, GroupAzure, SubscriptionAzure, TeamAzure
from univention.office365.udmwrapper.udmobjects import UDMOfficeUser, UDMOfficeGroup, UDMOfficeObject
from univention.office365.utils.utils import create_random_pw
from univention.office365.asyncqueue.queues.jsonfilesqueue import JsonFilesQueue
from univention.office365.logging2udebug import get_logger
from univention.office365.udmwrapper.subscriptions import SubscriptionProfile
from univention.office365.ucr_helper import UCRHelper

# logger = get_logger("office365", "o365")

'''
The classes contained in this module are the only ones with knowledge of UDM and Azure at the same time.
By design, in the rest of the code, it has been decided that everything related to Azure should be decoupled from
UDM/UCS and vice versa.

When the Listener is triggered by some operation for a user or a group several operations must be performed.
In a general way these operations can be defined as:
· Identify the changes in the operation.
· Update the data in Azure
· Update the data in UDM with the information from Azure.

Most of the operations for users and for groups are the same, but their execution is different.
An abstract `Connector` class has been defined from which the classes for users and for groups inherit.

			  ┌───────────────────┐       ┌─────────────────────┐
			  │                   │       │                     │
			  │     Connector     │       │ ConnectorAttributes │
			  │                 ◄─┼───────┤                     │
			  └────────┬──────────┘       └─────────────────────┘
					   │
		 ┌─────────────┴───────────────┐
		 │                             │
┌────────▼────────┐            ┌───────▼──────────┐
│                 │            │                  │
│  UserConnector  │            │  GroupConnector  │
│                 │            │                  │
└─────────────────┘            └──────────────────┘


Not all changes in UDM can be made, nor are all attributes reflected in Azure.
For the connector, a number of attributes and the behavior that the connector should have when processing these attributes have been defined:
· Sync: Attributes that you want to synchronize.
· Anonymize: Attributes to be synchronized but anonymize.
· Never: Attributes that are never to be synchronized.
· Static: Attributes that whatever they contain in UDM will be synchronized to Azure with a specific value.

These attributes can be defined in UCR variables and can be consulted in UCRHelper
with the prefix "office365/attributes/".

To keep these attributes in memory and to be able to operate on them, a `ConnectorAttributes` class has been defined.
'''


class ConnectorAttributes(UserDict):
	system = {
		"krb5KDCFlags",
		"krb5PasswordEnd",
		"krb5ValidEnd",
		"passwordexpiry",
		"sambaAcctFlags",
		"sambaKickoffTime",
		"shadowExpire",
		"shadowLastChange",
		"shadowMax",
		"univentionMicrosoft365Team",
		"univentionOffice365Enabled",
		"univentionOffice365ADConnectionAlias",
		"userexpiry",
		"userPassword",
	}
	default_adconnection_name = "defaultADconnection"

	def __init__(self, lazy_load=False, logger=None):
		# type: (bool, Optional["logging.Logger"]) -> None
		if six.PY2:
			UserDict.__init__(self)
		else:
			super(ConnectorAttributes, self).__init__()
		self.anonymize = set()
		self.never = set()
		self.sync = set()
		self.mapping = {}
		self.static = {}
		self.multiple = {}
		self.listener = None
		self.adconnection_filter = None
		self.not_migrated_to_v3 = None
		self.logger = logger or get_logger("{}.{}".format(__name__, self.__class__.__name__))
		if not lazy_load:
			self.update_attributes_from_ucr()
			self._sanitize()
			self._disjoint_attributes()

	def update_attributes_from_ucr(self):
		# type: () -> None

		ucr = UCRHelper

		self.not_migrated_to_v3 = ucr.is_false(UCRHelper.office365_migrate_adconnection_ucrv)

		for attribute in ['anonymize', 'never', 'sync']:
			setattr(self, attribute, set(UCRHelper.ucr_split_value("office365/attributes/{}".format(attribute))))
		for attribute in ['mapping', 'static']:
			setattr(self, attribute, UCRHelper.ucr_entries_to_dict("office365/attributes/{}/".format(attribute)))

		# find attributes that map to the same azure properties
		temp_dict = defaultdict(list)
		for k, v in self.mapping.items():
			temp_dict[v].append(k)
			# only if more than one attribute maps to the same azure property it stored in multiple
			if len(temp_dict[v]) > 1:
				self.multiple[v] = temp_dict[v]

		self.logger.debug("listener observing attributes: %r", [a for a in self.all if a not in self.system])
		self.logger.debug("listener is also observing: %r", sorted(list(self.system)))
		self.logger.debug("attributes mapping UCS->AAD: %r", self.mapping)
		self.logger.debug("attributes to sync anonymized: %r", self.anonymize)
		self.logger.debug("attributes to never sync: %r", self.never)
		self.logger.debug("attributes to statically set in AAD: %r", self.static)
		self.logger.debug("attributes to sync: %r", self.sync)
		self.logger.debug("attributes to sync from multiple sources: %r", self.multiple)
		# just for log readability
		# TODO: this are currently sets and can't be sorted
		# attrs.sort()
		# self.anonymize.sort()
		# self.never.sort()
		# self.sync.sort()

	@property
	def all(self):
		# type: () -> Set[str]
		return (set(self.static) | self.sync | self.anonymize | set(self.mapping.keys())) - self.never

	def _sanitize(self):
		# type: () -> None
		# check the attributes that are in all but have no mapping and are not system attributes
		no_mapping = [attribute for attribute in self.all if attribute not in self.mapping.keys() and attribute not in self.system]
		if no_mapping:
			self.logger.warning("No mappings for attributes %r found - ignoring.", no_mapping)
			[self.anonymize, self.static, self.sync] = utils.remove_elements_from_containers(containers=[self.anonymize, self.static, self.sync], elements=no_mapping)

		dangerous_attrs = ["univentionOffice365ObjectID", "UniventionOffice365Data"]
		if any([a in dangerous_attrs for a in self.all]):
			self.logger.warning("Nice try.")
			[self.sync, self.static, self.anonymize] = utils.remove_elements_from_containers(containers=[self.sync, self.static, self.anonymize], elements=dangerous_attrs)

	def _disjoint_attributes(self):
		# type: () -> None
		"""
		Recalculate attributes that are disjunct.
		"""
		# never > anonymize > static > sync
		[self.sync, self.static, self.anonymize] = utils.remove_elements_from_containers(containers=[self.sync, self.static, self.anonymize], elements=self.never)
		[self.static, self.sync] = utils.remove_elements_from_containers(containers=[self.static, self.sync], elements=self.anonymize)
		[self.sync] = utils.remove_elements_from_containers(containers=[self.sync], elements=self.static)


@six.add_metaclass(abc.ABCMeta)
class Connector(object):
	"""
	Base class for all connectors.
	The connector is responsible for the interaction between the UDM Objects and Azure ones.
	It defines the interface for all connectors with the needed methods to be implemented.
	The main logic about how to transfer the information for each AD connection is implemented here.
	Also, the mapping between UDM and Azure is implemented here in the `parse` method.
	If any of the operations made in the connector requires some additional actions, they are also implemented in the connector.
	For example, if the creation of a user also needs to create or a group, the connector should implement the logic for that.
	The common workflow in any of the methods is the following:
		1. The connector gets the UDM object.
		2. For each AD connection of the received object:
			- The connector gets the corresponding Azure object.
			- The connector performs the operation on the Azure object.
			- The connector updates the UDM object.
		3. The connector makes any additional actions needed for the operation.

	"""
	def __init__(self, alias_connections=None, logger=None):
		# type: (Dict[str, str], Optional["logging.Logger"]) -> None
		self.logger = logger or get_logger("{}.{}".format(__name__, self.__class__.__name__), "o365")
		# UCR can set a filter on the AD connections to be considered
		self.all_alias_connections = alias_connections or UCRHelper.get_adconnection_aliases()  # type: Dict[str, str]
		self.accounts = []  # type: List[AzureAccount]
		self._load_filtered_accounts()
		self.cores = {account.alias: MSGraphApiCore(account) for account in self.accounts}  # type: Dict[str, MSGraphApiCore]
		self.attrs = ConnectorAttributes(logger=self.logger)  # type: ConnectorAttributes

	def has_initialized_connections(self):
		# type: () -> bool
		return len(self.accounts) > 0

	def get_listener_filter(self):
		# type: () -> str
		res = ''
		filtered_in_aliases = UCRHelper.get_adconnection_filtered_in()
		for alias in filtered_in_aliases:
			if alias not in self.all_alias_connections:
				self.logger.warning('Alias {!r} from UCR {!r} not listed in UCR {!r}. Exiting.'.format(alias, UCRHelper.adconnection_filter_ucrv, UCRHelper.adconnection_alias_ucrv))
				continue
			if alias in self.cores.keys():
				res += filter_format('(univentionOffice365ADConnectionAlias=%s)', (alias,))
			else:
				self.logger.warning('Alias {!r} from UCR {!r} is not initialized. Exiting.'.format(alias, UCRHelper.adconnection_filter_ucrv))
				continue
		if len(res.split('=')) > 2:
			res = '(|{})'.format(res)
		return res

	def _load_filtered_accounts(self):
		# type: () -> None
		filtered_in_aliases = UCRHelper.get_adconnection_filtered_in() or list(self.all_alias_connections.keys())
		for alias in filtered_in_aliases:
			if alias not in self.all_alias_connections.keys():
				self.logger.warning('Alias {!r} from UCR {!r} not listed in UCR {!r}. Exiting.'.format(alias, UCRHelper.adconnection_filter_ucrv, UCRHelper.adconnection_alias_ucrv))
				continue
			account = AzureAccount(alias)
			if not account.is_initialized():
				self.logger.warning('Alias {!r} from UCR {!r} is not initialized. Exiting.'.format(alias, UCRHelper.adconnection_filter_ucrv))
				continue
			self.accounts.append(account)

	@abstractmethod
	def create(self, udm_object):
		# type: (UDMOfficeObject) -> None
		""""""
		raise NotImplementedError

	@abstractmethod
	def delete(self, udm_object):
		# type: (UDMOfficeObject) -> None
		""""""
		raise NotImplementedError

	@abstractmethod
	def modify(self, new_object, old_object):
		# type: (UDMOfficeObject, UDMOfficeObject) -> None
		""""""
		raise NotImplementedError

	# @abstractmethod
	# def invalidate_all_tokens(self, udm_object):
	# 	# type: (UDMOfficeObject) -> None
	# 	""""""
	# 	raise NotImplementedError
	#
	# @abstractmethod
	# def deactivate(self, udm_object):
	# 	# type: (UDMOfficeObject) -> None
	# 	""""""
	# 	raise NotImplementedError

	@abstractmethod
	def parse(self, udm_object, modify=False):
		# type: (UDMOfficeObject, bool) -> AzureObject
		""""""
		a = UserAzure()
		return a


class UserConnector(Connector):
	"""
	Specific connector with the related methods for the user.
	Local attributes:
		cores: For each AD connection, a core object is created and stored in this dictionary.
	Methods:
		create: create a user in Azure AD
			- For each AD connection:
				- The core object is got for that AD connection.
				- The Azure object is created.
				- The Azure object is updated with core object.
				- Create operation is executed in Azure User.
				- A subscription is assigned to the user.
				- All the Azure tokens are invalidated.
				- The UDM object is updated.
		delete: delete a user in Azure AD
			- For each AD connection:
				- The core object is got for that AD connection.
				- The Azure object is created.
				- The Azure object is updated with core object.
				- Delete operation is executed in Azure User.
				- The UDM object is updated.
				- Licenses are removed from the Azure user.
		modify: modify a user in Azure AD
			In this case the operations are split in two:
				- The ones for the modified AD connection aliases
					- The core object is got for that AD connection.
					- The Azure object is created for the new and old UDM objects.
					- The old Azure object is updated with core object.
					- Update operation is executed for old Azure User with new Azure object as reference
					- The new UDM object is updated with the data from the Azure object.
				- The ones for the AD connections to be deactivated.
					- The core object is got for that AD connection.
					- The Azure object is created from new UDM object.
					- The Azure object is updated with core object.
					- The Azure object is deactivated for the AD connection.
					- The UDM object is updated.
		parse: parse the UDM user object to Azure user object
		_attributes_to_update: given a list of considered attributes to update, return the ones that have been modified from old to new UDM object.
	"""

	def __init__(self, alias_connections=None, logger=None):
		# type: (Optional[Dict[str, str]], Optional[Logger]) -> None
		super(UserConnector, self).__init__(alias_connections, logger)
		self.group_connector = GroupConnector(alias_connections, logger)


	def _assign_subscription(self, udm_user, azure_user):
		# type: (UDMOfficeUser, UserAzure) -> None
		""""""
		msg_no_allocatable_subscriptions = 'User {}/{} created in Azure AD ({}), but no allocatable subscriptions' \
										   ' found.'.format(udm_user.username, azure_user.id, udm_user.current_connection_alias)
		msg_multiple_subscriptions = 'More than one usable Microsoft 365 subscription found.'

		subs_available = SubscriptionAzure.get_enabled(self.cores[udm_user.current_connection_alias], UCRHelper.get_service_plan_names())
		subs_available_index = {subs_sku.skuPartNumber: subs_sku for subs_sku in subs_available}
		self.logger.debug('seats in subscriptions_online: %r', list(subs_available_index.keys()))
		if len(subs_available) == 0:
			raise NoAllocatableSubscriptions(azure_user, msg_no_allocatable_subscriptions, udm_user.current_connection_alias)

		# get SubscriptionProfiles for users groups
		# TODO: test with groups
		users_group_dns = udm_user['groups']
		users_subscription_profiles = SubscriptionProfile.get_profiles_for_groups(users_group_dns)
		self.logger.info('SubscriptionProfiles found for %r (%s): %r', udm_user['uid'], udm_user.current_connection_alias, users_subscription_profiles)
		if not users_subscription_profiles:
			self.logger.warning('No SubscriptionProfiles: using all available subscriptions (%s).', udm_user.current_connection_alias)
			if len(subs_available) > 1:
				self.logger.warning(msg_multiple_subscriptions)
			azure_user.add_license(subs_available[0])
			return

		subscription_profile_to_use = None
		selected_subs_sku = None
		for subscription_profile in users_subscription_profiles:
			skuPartNumber = subscription_profile.subscription
			selected_subs_sku = subs_available_index.get(skuPartNumber)
			if selected_subs_sku:
				if selected_subs_sku.has_free_seats():
					subscription_profile.skuId = selected_subs_sku.skuId
					subscription_profile_to_use = subscription_profile
			else:
				self.logger.warning(
					'Subscription from profile %r (%s) could not be found in the enabled subscriptions in Azure.',
					subscription_profile, udm_user.current_connection_alias)
				selected_subs_sku = None
				continue

		if not subscription_profile_to_use:
			raise NoAllocatableSubscriptions(azure_user, msg_no_allocatable_subscriptions, udm_user.current_connection_alias)

		self.logger.info(
			'Using subscription profile %r (skuId: %r).',
			subscription_profile_to_use,
			subscription_profile_to_use.skuId)

		# calculate plan restrictions
		# get all plans of this subscription
		if subscription_profile_to_use.whitelisted_plans:
			deactivate_plans = set(selected_subs_sku.get_plans_names()) - set(subscription_profile_to_use.whitelisted_plans)
		else:
			deactivate_plans = set()
		deactivate_plans.update(subscription_profile_to_use.blacklisted_plans)
		self.logger.info('Deactivating plans %s (%s).' % (deactivate_plans, udm_user.current_connection_alias))
		deactivate_plan_ids = selected_subs_sku.get_plans_id_from_names(deactivate_plans)
		azure_user.add_license(selected_subs_sku, deactivate_plan_ids)

	@staticmethod
	def prepare_azure_attributes(azure_user, to_remove=False):
		# type: (UserAzure, bool) -> Mapping[str,str]
		""""""
		if to_remove:
			return {"objectId": azure_user.id}
		else:
			return {"objectId": azure_user.id, "userPrincipalName": azure_user.userPrincipalName}

	def new_or_reactivate_user(self, udm_object):
		# type: (UDMOfficeUser) -> None
		""""""
		alias = udm_object.current_connection_alias
		assert alias in self.cores, "Alias {} not exist in {}".format(alias, self.cores)
		user_azure = self.parse(udm_object)
		user_azure.create_or_modify()
		try:
			try:
				self._assign_subscription(udm_user=udm_object, azure_user=user_azure)
			except AddLicenseError as exc:
				self.logger.warning('Could not add license for subscription %r to user %r: %s', exc.user_id, exc.sku_id, exc)
			user_azure.invalidate_all_tokens()
		except NoAllocatableSubscriptions as exc:
			self.logger.warning('(%r) Not subscription located for user %r: %s', exc.adconnection_alias, exc.user.id, exc)
		udm_object.create_azure_attributes(self.prepare_azure_attributes(user_azure), alias)
		self.logger.info("User creation success. userPrincipalName: %r objectId: %r dn: %s adconnection: %s", user_azure.userPrincipalName, user_azure.id, udm_object.dn, udm_object.current_connection_alias)
		# create groups (if any) and if must be synced "office365/groups/sync".
		# Check old office365-user.py:new_or_reactivate_user
		# If groups need to be synced
		if UCRHelper.is_true(UCRHelper.group_sync_ucrv, False):
			# Loop over the groups of the user
			for group_dn in udm_object.get("groups"):
				# Create a UDM representation of the group
				udm_office_group = UDMOfficeGroup({}, ldap_cred=udm_object.ldap_cred, dn=group_dn)
				# If the group have any nested user that is in azure, group needs to be synced
				with udm_office_group.set_current_alias(alias):
					# if the group is not synced for the current connection, sync it
					if alias not in udm_office_group.adconnection_aliases:
						group_azure = self.group_connector._create_group(udm_office_group)

						self.logger.info("Created group with displayName: %r (%r) adconnection: %s", group_azure.displayName, group_azure.id, alias)
						# check if the new group is also a team - and needs to be configured as team
						if udm_office_group.is_team():
							self.group_connector.convert_group_to_team(udm_office_group, group_azure)
					else:
						self.group_connector.add_member(udm_office_group, udm_object)

	# new_or_reactivate_user
	def create(self, udm_object):
		# type: (UDMOfficeUser) -> None
		"""
		Given an UDMOfficeUser object, create a new user in Azure.

		"""
		if udm_object.should_sync():
			for alias in udm_object.aliases():
				self.new_or_reactivate_user(udm_object)

	# univention.office365.azure_handler.AzureHandler.delete_user
	def delete(self, udm_object):
		# type: (UDMOfficeUser) -> None
		""""""
		for alias in udm_object.aliases():
			assert alias in self.cores, "Alias {} not exist".format(alias)
			user_azure = self.parse(udm_object)
			# univention.office365.listener.Office365Listener.delete_user
			# https://msdn.microsoft.com/Library/Azure/Ad/Graph/howto/azure-ad-graph-api-permission-scopes#DirectoryRWDetail
			#
			# MS has changed the permissions: "due to recent security enhancement to AAD the application which is
			# accessing the AAD through Graph API should have a role called Company Administrator"...
			#
			#
			# https://github.com/Azure-Samples/active-directory-dotnet-graphapi-console/issues/27
			# https://support.microsoft.com/en-us/kb/3004133
			# http://stackoverflow.com/questions/31834003/azure-ad-change-user-password-from-custom-app
			#
			# So for now use deactivate_user() instead of _delete_objects().
			#
			# TODO: try/except? check if resource not found or deleted ok
			# user_azure.delete()

			user_azure.deactivate(rename=True)
			# udm_object.modify_azure_attributes(None)  # it's not needed because the object was remove form udm

			self.logger.info(
				"User deletion success. userPrincipalName: %r objectId: %r dn: %s adconnection: %s",
				user_azure.userPrincipalName, user_azure.id, udm_object.dn, udm_object.current_connection_alias
			)

	def modify(self, old_object, new_object):
		# type: (UDMOfficeUser, UDMOfficeUser) -> None
		"""
		Use cases:
			Activate one or more alias
				User with groups
				User without groups
				User is owner of groups
			Deactivate one or more alias
				User with groups
				User without groups
				User is owner of groups
			Attrs modify
		"""
		# TODO: use some kind of cache for the parsed objects (udm_object => parsed_object)
		if not old_object.should_sync() and new_object.should_sync():
			for alias in new_object.aliases():
				self.new_or_reactivate_user(new_object)
				return
		elif old_object.should_sync() and not new_object.should_sync():
			for alias in old_object.aliases():
				old_azure = self.parse(old_object)
				old_azure.deactivate(rename=True)
				new_object.modify_azure_attributes(self.prepare_azure_attributes(old_azure, to_remove=True))
				return

		if new_object.should_sync():
			#####
			# NEW or REACTIVATED account
			#####
			for alias in new_object.get_diff_aliases(old_object):
				with new_object.set_current_alias(alias):
					self.new_or_reactivate_user(new_object)

			#####
			# Remove connection
			#####
			for alias in old_object.get_diff_aliases(new_object):
				with new_object.set_current_alias(alias), old_object.set_current_alias(alias):
					old_azure = self.parse(old_object)
					old_azure.deactivate(rename=True)
					new_object.modify_azure_attributes(self.prepare_azure_attributes(old_azure, to_remove=True))

			#####
			# Modify attrs
			#####
			for alias in new_object.alias_to_modify(old_object):
				with new_object.set_current_alias(alias), old_object.set_current_alias(alias):
					old_azure = self.parse(old_object, set_password=False)
					new_azure = self.parse(new_object, set_password=False)
					data = old_azure.update(new_azure)
					if data:
						if new_azure.userPrincipalName != old_azure.userPrincipalName:
							new_object.modify_azure_attributes(self.prepare_azure_attributes(new_azure))
						self.logger.info("User modification success. userPrincipalName: %r objectId: %r dn: %s adconnection: %s", new_azure.userPrincipalName, new_azure.id, new_object.dn, new_object.current_connection_alias)
					else:
						self.logger.info("User have no data to be modified. %r objectId: %r dn: %s adconnection: %s", new_azure.userPrincipalName, new_azure.id, new_object.dn, new_object.current_connection_alias)

	# def _attributes_to_update(self, considered_attributes, new_object, old_object):
	# 	# type: (Iterable, UDMOfficeUser, UDMOfficeUser) -> List[str]
	# 	"""
	#
	# 	"""
	# 	fields_changed = new_object.modified_fields(old_object)
	# 	return [attribute for attribute in considered_attributes if attribute in fields_changed]

	@staticmethod
	def anonymize_attr(value):
		# type: (Any) -> str
		# FIXME: txt is unused
		return uuid.uuid4().hex

	def parse(self, udm_user, modify=False, set_password=True):
		# type: (UDMOfficeUser, bool) -> UserAzure
		# anonymize > static > sync
		# get values to sync
		res = dict()
		core = self.cores[udm_user.current_connection_alias]  # type: MSGraphApiCore

		for attr in self.attrs.all:
			if attr in self.attrs.system:
				# filter out univentionOffice365Enabled and account deactivation/locking attributes
				continue
			elif attr not in udm_user.udm_object_reference.oldattr and not modify:
				# only set empty values to unset properties when modifying
				continue
			elif attr in self.attrs.anonymize:
				tmp = self.anonymize_attr(getattr(udm_user, attr))
			elif attr in self.attrs.static:
				tmp = self.attrs.static[attr]
			elif attr in self.attrs.sync:
				tmp = getattr(udm_user, attr)  # Azure does not like empty strings - it wants None!
			else:
				raise RuntimeError("Attribute to sync {!r} is not configured through UCR.".format(attr))

			if attr in res:
				if isinstance(res[attr], list):
					res[attr].append(tmp)
				else:
					raise RuntimeError("Office365Listener._get_sync_values() res[{}] already exists with type {} and value '{}'.".format(attr, type(res[attr]), res[attr]))
			else:
				# if hasattr(tmp, '__len__'):
				# 	if tmp and len(tmp) == 1:
				# 		res[attr] = tmp[0]
				# 	else:
				# 		res[attr] = tmp
				# else:
				res[attr] = tmp

		# build data dict to build AzureObject
		data = {}
		user_azure_fields = UserAzure.get_fields()
		for udm_key, azure_key in self.attrs.mapping.items():
			if udm_key in res:
				value = res.get(udm_key)
				if azure_key in list(self.attrs.multiple.keys()):
					if isinstance(value, list):
						if azure_key not in data:
							data[azure_key] = value
						else:
							data[azure_key].extend(value)
					else:
						if azure_key not in data:
							data[azure_key] = [value]
						else:
							data[azure_key].append(value)
				elif (user_azure_fields.get(azure_key) == list and not isinstance(value, list)):
					if azure_key not in data:
						data[azure_key] = [value]
					else:
						data[azure_key].append(value)
				else:
					if not isinstance(value, user_azure_fields.get(azure_key)):
						old_value = value
						if hasattr(value, "__len__"):
							if len(value) == 0:
								value = None
								continue
							elif len(value) == 1:
								value = value[0]
							else:
								value = value[0]
						self.logger.warning("Warning not same type {azure_key}: {old_value} not is a {type}. Taken {new_value}".format(azure_key=azure_key, old_value=old_value, type=user_azure_fields.get(azure_key), new_value=value))
					if hasattr(value, "__len__"):
						if len(value) == 0:
							value = None
							continue
					data[azure_key] = value

		# mandatory attributes, not to be overwritten by user
		local_part_of_email_address = udm_user.mailPrimaryAddress.rpartition("@")[0]
		mandatory_attributes = dict(id=udm_user.azure_object_id,
									onPremisesImmutableId=udm_user.entryUUID,
									accountEnabled=True,
									userPrincipalName="{0}@{1}".format(local_part_of_email_address, core.account["domain"]),
									mailNickname=local_part_of_email_address,
									displayName=data.get("displayName", "no name"),
									usageLocation=udm_user.get("st") or UCRHelper.get_usage_location()
									)
		if set_password:
			mandatory_attributes.update(dict(passwordProfile=dict(password=create_random_pw(), forceChangePasswordNextSignInWithMfa=False)))
		data.update(mandatory_attributes)
		if len(data.get("businessPhones", [])) > 1:
			data["businessPhones"] = [data["businessPhones"][0]]
		if "otherMails" in data:
			data["otherMails"] = list(set(data["otherMails"]))
		user_azure = UserAzure(**data)
		user_azure.set_core(core)
		return user_azure

	# def invalidate_all_tokens(self, udm_object):
	#	# type: (Udm) -> None
	# 	""""""
	# 	for alias in udm_object.aliases():
	# 		user_azure = self.parse(udm_object)
	# 		user_azure.invalidate_all_tokens()

	def deactivate(self, udm_object):
		# type: (UDMOfficeUser) -> None
		""""""
		for alias in udm_object.aliases():
			assert alias in self.cores, "Alias {} not exist".format(alias)
			user_azure = self.parse(udm_object)
			user_azure.deactivate(rename=True)
			udm_object.modify_azure_attributes(self.prepare_azure_attributes(user_azure, to_remove=True))

			self.logger.info(
				"User deactivation success. userPrincipalName: %r objectId: %r dn: %s adconnection: %s",
				user_azure.userPrincipalName, user_azure.id, udm_object.dn, udm_object.current_connection_alias
			)

# def get_direct_groups(self, user):
#	# type: (UDMOfficeUser) -> None
# 	""""""
#
# def reset_password(self, user):
#	# type: (UDMOfficeUser) -> None
# 	""""""
#
# def add_license(self, user):
#	# type: (UDMOfficeUser) -> None
# 	""""""
#
# def remove_license(self, user):
#	# type: (UDMOfficeUser) -> None
# 	""""""


class GroupConnector(Connector):
	"""
	Specific connector with the related methods for the group.
	Local attributes:
		cores: For each AD connection, a core object is created and stored in this dictionary.
	Methods:
		create: create a group in Azure AD
			-

		delete: delete a group in Azure AD

		modify: modify a group in Azure AD

		parse: parse the UDM group object to Azure group object
		_attributes_to_update: given a list of considered attributes to update, return the ones that have been modified from old to new UDM object.
	"""

	def __init__(self, alias_connections=None, logger=None):
		# type: (Optional[Dict[str, str]], Optional[Logger]) -> None
		super(GroupConnector, self).__init__(alias_connections, logger)
		self.attrs = {"cn", "description", "uniqueMember", "univentionMicrosoft365Team", "univentionMicrosoft365GroupOwners"}
		self.async_task = True

	@staticmethod
	def prepare_azure_attributes(azure_group):
		# type: (GroupAzure) -> Mapping[str,str]
		""""""
		return {"objectId": azure_group.id}

	def create(self, udm_object):
		# type: (UDMOfficeGroup) -> None
		""""""
		"""
		if self.udm.group_in_azure(dn):
			new_group = self.create_group_from_new(new, dn)
			# save Azure objectId in UDM object
			udm_group = self.udm.get_udm_group(dn)
			self.set_adconnection_object_id(udm_group, new_group["objectId"])
			logger.info("Created group with displayName: %r (%r) adconnection: %s", new_group["displayName"], new_group["objectId"], udm_user.current_connection_alias)
			# check if the new group is also a team - and needs to be configured as team
			if new.get('univentionMicrosoft365Team'):
				self.convert_group_to_team(group=new_group, new=new)
		"""
		# Check if group exists in azure
		for alias in udm_object.aliases(set(self.cores.keys())):
			if udm_object.in_azure():
				group_azure = self._create_group(udm_object)

				self.logger.info("Created group with displayName: %r (%r) adconnection: %s", group_azure.displayName, group_azure.id, alias)
				# check if the new group is also a team - and needs to be configured as team
				if udm_object.is_team():
					self.convert_group_to_team(udm_object, group_azure)
			# TODO: check if we need to add grpup owners to the team here

	def _create_group(self, udm_object):
		# type: (UDMOfficeGroup) -> GroupAzure
		group_azure = self.parse(udm_object)
		group_azure.create_or_modify()
		udm_object.modify_azure_attributes(self.prepare_azure_attributes(group_azure))
		self.add_ldap_members_to_azure_group(udm_object, group_azure)
		return group_azure

	def add_ldap_members_to_azure_group(self, udm_object, azure_object):
		# type: (UDMOfficeGroup, GroupAzure) -> None
		"""
		Recursively look for users and groups to add to the Azure group.

		:param group_dn: DN of UDM group
		:param object_id: Azure object ID of group to add users/groups to
		:return: None
		"""
		self.logger.debug("group_dn=%r object_id=%r adconnection_alias=%r", udm_object.dn, azure_object.id, udm_object.current_connection_alias)

		users_and_groups_to_add = udm_object.get_users_from_ldap()

		for group in udm_object.get_nested_groups_with_azure_users():
			if group is not udm_object:
				if not group.azure_object_id:
					azure_group = self._create_group(group)
				if group.dn in udm_object.get_nested_group():
					users_and_groups_to_add.append(group.azure_object_id)

		# add users to groups
		azure_object.add_members(users_and_groups_to_add)

		# search tree upwards, create groups as we go, don't add users
		for group in udm_object.get_groups_member_of_not_in_azure():
			self._create_group(group)

	# TODO: check if we need to return the deleted group information
	def delete(self, udm_object):
		# type: (UDMOfficeGroup) -> None
		""""""
		for alias in udm_object.aliases(set(self.cores.keys())):
			if not udm_object.azure_object_id:
				self.logger.error("Couldn't find object_id for group %r (%s), cannot delete.", udm_object.get("cn"), alias)
				continue
			try:
				if udm_object.is_team():
					try:
						team = TeamAzure(id=udm_object.azure_object_id)
						team.set_core(self.cores[alias])
						team.deactivate()
						self.logger.info("Deleted team %r from Azure AD %r", udm_object.get("cn"), alias)
					except MSGraphError as g_exc:
						self.logger.error("Error while deleting team %r: %r.", udm_object.get("cn"), g_exc)
				azure_group = self.parse(udm_object)
				azure_group.remove_direct_members()
				azure_group.deactivate()
				self.logger.info("Deleted group %r from Azure AD '%r'", udm_object.get("cn"), alias)
			except MSGraphError as g_exc:
				self.logger.error("Group %r didn't exist in Azure: %r.", udm_object.get("cn"), g_exc)

	def modify(self, old_udm_group, new_udm_group):
		# type: (UDMOfficeGroup, UDMOfficeGroup) -> None
		""""""
		# Groups alias depends directly from the aliases of it member users
		# We need to look over all the available connections
		for alias in new_udm_group.aliases(set(self.cores.keys())):
			with old_udm_group.set_current_alias(alias):
				if new_udm_group.in_azure() or \
						alias in new_udm_group.adconnection_aliases or \
						alias in old_udm_group.adconnection_aliases:

					modification_attributes_udm_group = old_udm_group.diff_keys(new_udm_group)
					object_id = old_udm_group.azure_object_id or new_udm_group.azure_object_id

					# No modification to be considered
					if not (self.attrs & modification_attributes_udm_group):
						self.logger.info("No modifications found, ignoring.")
						if object_id:
							new_udm_group.modify_azure_attributes(self.prepare_azure_attributes(GroupAzure(id=object_id)))
						continue

					# TODO We believe that it's unneeded
					# for ignore_attribute in ["univentionMicrosoft365Team"]:
					# 	if ignore_attribute in modification_attributes:
					# 		modification_attributes.remove(ignore_attribute)

					# We are getting the group from azure and not parsing it from UDM objects
					# because it could be removed manually from azure but exists in UDM. In this case
					# we create the group again in Azure.
					if not object_id:
						# just create a new group
						self.logger.info("No objectID for group %r found, creating a new azure group...", old_udm_group.dn or new_udm_group.dn)
						azure_group = self._create_group(new_udm_group)
					# modification_attributes_udm_group = new_udm_group
					else:
						try:
							azure_group = GroupAzure.get(self.cores[new_udm_group.current_connection_alias], object_id)
						except MSGraphError:
							self.logger.warning("Office365Listener.modify_group() azure group doesn't exist (anymore), creating it instead.")
							azure_group = self._create_group(new_udm_group)
						# modification_attributes_udm_group = new_udm_group

					# If the azure group is deactivates, reactivate
					if azure_group.is_delete():
						self.logger.info("Reactivating azure group %r...", azure_group.displayName)
						new_azure_group = self.parse(new_udm_group)
						azure_group.update(new_azure_group)
					# TODO: unarchive team
					# modules/univention/office365/listener.py:607
					# try:
					# 	team_azure = TeamAzure.get(self.cores[new_udm_group.current_connection_alias], object_id)
					# 	team_azure.reactivate()
					# except MSGraphError:
					# 	pass

					# Check team modifications
					self.check_and_modify_teams(old_udm_group, new_udm_group, azure_group)

					# Check owners modifications
					self.check_and_modify_owners(old_udm_group, new_udm_group, azure_group)

					# Check members modifications
					self.check_and_modify_members(old_udm_group, new_udm_group, azure_group)

					# Check other attributes
					self.check_and_modify_attributes(new_udm_group, azure_group)

					# add owner before removing them. If a group has an owner, removing the last owner will fail

	def delete_empty_group(self, azure_group, udm_group=None):
		# type: (GroupAzure, Optional[UDMOfficeGroup]) -> bool
		"""
		Recursively look if a group or any of it parent groups is empty and remove it.
		:param group_id: str: object id of group (and its parents) to check
		:return: bool: if the group was deleted
		"""
		self.logger.debug("group_id=%r (%s)", azure_group.id, udm_group.current_connection_alias)

		# get IDs of groups this group is a member of before deleting it
		nested_parent_groups = azure_group.member_of()

		# check members
		# members = self.ah.get_groups_direct_members(group_id)["value"]
		members = azure_group.list_members()
		if members:
			# TODO, find another way to check for active members
			# this for member_id ...
			#          self.ah.list_users
			# is just too expensive,
			# think about it, if we have a group with 100 members and we create another
			# 100 users (members of that group) this creates over 10000 requests

			# member_ids = self.ah.directory_object_urls_to_object_ids(members)
			# azure_objs = list()
			# for member_id in member_ids:
			#	try:
			#		azure_objs.append(self.ah.list_users(objectid=member_id))
			#	except ResourceNotFoundError:
			#		# that's OK - it is probably not a user but a group
			#		try:
			#			azure_objs.append(self.ah.list_groups(objectid=member_id))
			#		except ResourceNotFoundError:
			#			# ignore
			#			logger.error("Office365Listener.delete_empty_group() found unexpected object in group: %r, ignoring.", member_id)
			# if all(azure_obj["mailNickname"].startswith("ZZZ_deleted_") for azure_obj in azure_objs):
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
			# else:
			self.logger.debug("Group has active members, not deleting it.")
			return False
		else:
			self.logger.info("Removing empty group %r (%s)...", azure_group.id, udm_group.current_connection_alias)
			azure_group.remove_direct_members()
			azure_group.deactivate()
			if not udm_group:
				self.logger.error("Office365Listener.delete_empty_group() failed to find own group: %r, ignoring.", azure_group.id)
			else:
				udm_group.deactivate_azure_attributes()

		# check parent groups
		for azure_nested_parent in nested_parent_groups:
			udm_office_nested_parent = UDMOfficeGroup.get_other_by_displayName(azure_group.displayName, udm_group.ldap_cred)
			if not udm_office_nested_parent:
				self.delete_empty_group(azure_nested_parent)
			with udm_office_nested_parent.set_current_alias(udm_group.current_connection_alias):
				self.delete_empty_group(azure_nested_parent, udm_office_nested_parent)

		return True

	def convert_group_to_team(self, udm_group, azure_group):
		# type: (UDMOfficeGroup, GroupAzure) -> None
		sub_task = []
		for owner_udm in udm_group.get_owners():
			with owner_udm.set_current_alias(udm_group.current_connection_alias):
				task = azure_group.add_owner(owner_udm.azure_object_id, async_task=self.async_task)
				if self.async_task:
					sub_task.append(task)
		if self.async_task:
			task = TeamAzure.create_from_group_async(udm_group.current_connection_alias, azure_group.id, sub_task)
			q = JsonFilesQueue("o365asyncqueue")
			q.enqueue(task)
		else:
			TeamAzure.create_from_group(self.cores[udm_group.current_connection_alias], azure_group.id)

	def check_and_modify_teams(self, old_udm_group, new_udm_group, azure_group):
		# type: (UDMOfficeGroup, UDMOfficeGroup, GroupAzure) -> None
		alias = old_udm_group.current_connection_alias
		# New Team
		if not old_udm_group.is_team() and new_udm_group.is_team():
			self.convert_group_to_team(new_udm_group, azure_group)

		# Remove Team from group
		elif old_udm_group.is_team() and not new_udm_group.is_team():
			try:
				team_azure = TeamAzure(id=azure_group.id)
				team_azure.deactivate()
				self.logger.info("Deleted team %r from Azure AD %r", azure_group.displayName, alias)
			except MSGraphError as g_exc:
				self.logger.error("Error while deleting team %r: %r.", azure_group.displayName, g_exc)

	# TODO: from univention.office365.listener.Office365Listener.modify_group
	def check_and_modify_owners(self, old_udm_group, new_udm_group, azure_group):
		# type: (UDMOfficeGroup, UDMOfficeGroup, GroupAzure) -> None
		alias = old_udm_group.current_connection_alias
		added_owners, removed_owners = old_udm_group.owners_changes(new_udm_group)

		for owner in added_owners:
			try:
				self.logger.info("Add owner %r to group %r from Azure AD %r", owner.dn, azure_group.displayName, alias)
				with owner.set_current_alias(alias):
					azure_group.add_owner(owner.azure_object_id)
			except MSGraphError as g_exc:
				self.logger.error("Error while adding group owner to %r: ", azure_group.displayName)
				self.logger.error(g_exc)

		for owner in removed_owners:
			try:
				self.logger.info("Remove owner %r from group %r from Azure AD %r", owner.dn, azure_group.displayName, old_udm_group.current_connection_alias)
				with owner.set_current_alias(alias):
					azure_group.remove_owner(owner.azure_object_id)
			except MSGraphError as g_exc:
				self.logger.error("Error while removing group owner to %r: ", azure_group.displayName)
				self.logger.error(g_exc)
	# TODO it's really need???
	# Do not sync this to any azure attribute directly
	# modification_attributes_udm_group.remove("univentionMicrosoft365GroupOwners")

	#  Owners: udm_object.owners()
	#   - add owners
	#   - remove owners
	#   - [remove univentionMicrosoft365GroupOwners to not be synced]

	# From: univention.office365.listener.Office365Listener.modify_group
	def check_and_modify_members(self, old_udm_group, new_udm_group, azure_group):
		# type: (UDMOfficeGroup, UDMOfficeGroup, GroupAzure) -> None
		alias = new_udm_group.current_connection_alias
		added_members_dn, removed_members_dn = old_udm_group.members_changes(new_udm_group)
		self.logger.info("dn=%r added_members=%r removed_members=%r", old_udm_group.dn, added_members_dn, removed_members_dn)
		# add new members to Azure
		users_and_groups_to_add = []

		for added_member_dn in added_members_dn:
			if added_member_dn in new_udm_group.get_users():
				# it's a user
				try:
					udm_user = UDMOfficeUser({}, new_udm_group.ldap_cred, dn=added_member_dn)
				except univention.admin.uexceptions.noObject as e:
					self.logger.warning("UDM User: %r has been removed. Not syncing with azure %r", added_member_dn, alias)
					continue
				if udm_user.is_enable():
					with udm_user.set_current_alias(alias):
						if udm_user.azure_object_id:
							users_and_groups_to_add.append(udm_user.azure_object_id)
			elif added_member_dn in new_udm_group.get_nested_group():
				# it's a group
				# check if this group or any of its nested groups has azure_users
				try:
					udm_office_add_member_group = UDMOfficeGroup({}, new_udm_group.ldap_cred, added_member_dn)
				except univention.admin.uexceptions.noObject as e:
					self.logger.warning("UDM Group: %r has been removed. Not syncing with azure %r", added_member_dn, alias)
					continue
				with udm_office_add_member_group.set_current_alias(alias):
					for group in udm_office_add_member_group.get_nested_groups_with_azure_users():
						if isinstance(group, UDMOfficeGroup):
							if not group.azure_object_id:
								self._create_group(group)
							if group.dn in udm_office_add_member_group.get_nested_group():
								users_and_groups_to_add.append(group.azure_object_id)
			else:
				raise RuntimeError("Office365Listener.modify_group() {!r} from new[uniqueMember] not in "
								   "'nestedGroup' or 'users' ({!r}).".format(added_member_dn, alias))

		azure_group.add_members(users_and_groups_to_add)

		# remove members
		for removed_member_dn in removed_members_dn:
			if removed_member_dn in old_udm_group.get_users():
				# it's a user
				try:
					udm_user = UDMOfficeUser({}, new_udm_group.ldap_cred, dn=removed_member_dn)  # TODO find the way to get azure id without UDMUser maybe with caching the last remove operation
				except univention.admin.uexceptions.noObject as exc:
					self.logger.warning("User dn: %r not exist in UDM, aborting remove member.", removed_member_dn)
					continue
				if udm_user.azure_object_id:
					azure_group.remove_member(udm_user.azure_object_id)
				else:
					self.logger.warning("Office365Listener.modify_group(), removing members: couldn't figure out object name from dn %r", removed_member_dn)
			elif removed_member_dn in old_udm_group.get_nested_group():
				# it's a group
				# check if this group or any of its nested groups has azure_users
				try:
					udm_office_remove_member_group = UDMOfficeGroup({}, new_udm_group.ldap_cred, removed_member_dn)
				except univention.admin.uexceptions.noObject as exc:
					self.logger.warning("Group dn: %r not exist in UDM, aborting remove member.", removed_member_dn)
					continue
				member_id = udm_office_remove_member_group.azure_object_id
				if not member_id:
					try:
						azure_remove_member_group = GroupAzure.get_by_name(self.cores[alias], udm_office_remove_member_group.displayName)
					except GraphRessourceNotFroundError as e:
						azure_remove_member_group = None
					member_id = azure_remove_member_group.id if azure_remove_member_group else None
				if member_id:
					azure_group.remove_member(member_id)
				else:
					self.logger.warning("Office365Listener.modify_group(), removing members: couldn't figure out object name from dn %r", removed_member_dn)
			else:
				raise RuntimeError("Office365Listener.modify_group() {!r} from old[uniqueMember] not in "
								   "'nestedGroup' or 'users' ({!r}).".format(removed_member_dn, alias))

		if removed_members_dn and not added_members_dn:
			deleted = self.delete_empty_group(azure_group, new_udm_group)
			if deleted:
				return None  # TODO ????

	#   - Split uniqueMember into added and removed members
		#   - split the uniqueMember into users and groups udm_object.user_members(), udm_object.group_members()
		#   - for Added members:
		#     - Check if its an user of the group (add to azure)
		#     - Check if its a nested group
		#       - if it have any azure users, add to azure udm_group.azure_users()
		#   	- check if nested group is in azure and if it needs to be created
		#     - Add the users and groups to the group
		#   - for Removed members:	modules/univention/office365/listener.py:698

	def check_and_modify_attributes(self, new_udm_group, azure_group):
		# type: (UDMOfficeGroup, GroupAzure) -> None
		new_azure_group = self.parse(new_udm_group)
		if (azure_group - new_azure_group).get_not_none_values_as_dict():
			azure_group.update(new_azure_group)
			return None  # TODO ????

	def add_member(self, udm_office_group, udm_office_user, alias=None):
		# type: (UDMOfficeGroup, UDMOfficeUser, str) -> None
		"""
		Given a UDMOfficeGroup and a UDMOfficeUser, add the user as a group member in azure.
		"""
		assert udm_office_group.current_connection_alias or alias
		alias = udm_office_group.current_connection_alias or alias
		with udm_office_group.set_current_alias(alias):
			azure_group = self.parse(udm_office_group)
			try:
				azure_group.add_member(udm_office_user.azure_object_id)
			except MSGraphError as e:
				if hasattr(e.response, "json"):
					body = e.response.json()
					if body.get("error",{}).get("message", "") == "One or more added object references already exist for the following modified properties: 'members'.":
						self.logger.warning("User %r has already been member of %r" % (azure_group.id, udm_office_user.azure_object_id))
						return
				raise

	def remove_member(self, udm_office_group, udm_office_user, alias=None):
		# type: (UDMOfficeGroup, UDMOfficeUser, Optional[str]) -> None
		"""
		Given a UDMOfficeGroup and a UDMOfficeUser, remove the user as a group member in azure.
		"""
		assert udm_office_group.current_connection_alias or alias
		alias = udm_office_group.current_connection_alias or alias
		with udm_office_group.set_current_alias(alias):
			azure_group = self.parse(udm_office_group)
			azure_group.remove_member(udm_office_user.azure_object_id)

	def parse(self, udm_group, modify=False):
		# type: (UDMOfficeGroup, bool) -> GroupAzure
		# anonymize > static > sync
		# get values to sync
		core = self.cores[udm_group.current_connection_alias]  # type: MSGraphApiCore

		data = dict(id=udm_group.azure_object_id, description=udm_group.description or None, displayName=udm_group.cn, mailEnabled=False, mailNickname=udm_group.cn.replace(" ", "_-_"), securityEnabled=True)
		group_azure = GroupAzure(**data)
		group_azure.set_core(core)
		return group_azure
