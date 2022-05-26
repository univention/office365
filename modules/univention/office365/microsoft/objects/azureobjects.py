import re
import sys
import time
from abc import abstractmethod
import abc
from typing import List, Dict, Any, Union, Optional

# from dataclasses import dataclass, fields
import attr
from six import reraise

from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError, AddLicenseError
from univention.office365.utils.utils import create_random_pw
from univention.office365.asyncqueue.tasks.azuretask import MSGraphCoreTask

delete_name_pattern = "ZZZ_deleted_{time}_{orig}"


"""
                                        ┌─────┐
                                        │Token│
                                        └──┬──┘
                                           │
                                           │
                                           │
                                           │
                                           │
                                     ┌─────┴────┐
                                     │     ▼    │               │
                                     │  Azure   │               │
                                     │  Account │               │
        ┌───────┐                    │          │               │
        │Azure  │                    └─────┬────┘               │
        │User  ◄├────────────┐             │                    │
        └───────┘            │             │                    │
                             │             │                    │
       ┌────────┐            │             │                    │                  .-~~~-.
       │ Azure ◄├────────────┤        ┌────┴────┐◄─────────────►│          .- ~ ~-(       )_ _
       │ Group  │            │        │    ▼    │               │         /        Microsoft    ~ -.
       └────────┘            ├────────┤  Azure  │    Requests   │        |         Graph             \
                             │        │  Core   │◄─────────────►│         \        API              .'
     ┌──────────┐            │        │         │               │           ~- . _____________ . -~
     │  Azure   │            │        └─────────┘◄─────────────►│
     │  Team   ◄├────────────┤                                  │
     └──────────┘            │                                  │
                             │                                  │
┌───────────────┐            │                                  │
│               │            │                                  │
│ Azure         │            │                                  │
│ Subscription ◄├────────────┘                                  │
│               │                                               │
└───────────────┘                                               │
                                                                │
                                                                │
                                                                │
"""

@attr.s
class AzureObject(metaclass=abc.ABCMeta):
	"""
	Base class for all Azure objects.
	The valid Azure attributes are defined in the class attributes.
	Methods:
		- get_not_none_values_as_dict: returns a dict with all attributes that are not None
		- __sub__: return a new AzureObject with the attributes that are not None and different from the `other` object.
		- set_core: set the core object to be used to communicate with the Azure API.
		_ _update_from_dict: update the attributes of the object from a dict (only the keys that are in the class attributes).
		- wait_for_operation: wait for a core operation to finish.
		- add_license: add a license to the object.
		- remove_license: remove a license from the object.
	Abstract methods:
		- create: create the object in the Azure API.
		- update: update the object in the Azure API.
		- delete: delete the object in the Azure API.
		- deactivate: deactivate the object in the Azure API.
		- activate: activate the object in the Azure API.
		- get: get the object from the Azure API.
		- list: # TODO: what is this expected to return?
	"""
	assignedLicenses = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  #: List[Dict[str, str]]
	calendar = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  #: Dict[str, str]
	calendarView = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  #: List[Dict[str, str]]
	createdDateTime = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	displayName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	drive = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  #: Dict[str, str]
	events = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  #: List[Dict[str, str]]
	id = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	mail = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	mailNickname = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	memberOf = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  #: List[Dict[str, str]]
	onPremisesLastSyncDateTime = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	onPremisesProvisioningErrors = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  #: List[Dict[str, str]]
	onPremisesSecurityIdentifier = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	onPremisesSyncEnabled = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  #: bool
	photo = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  #: Dict[str, str]
	preferredDataLocation = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	proxyAddresses = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  #: List[str]
	preferredLanguage = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	_core = None  # type: Union['MSGraphApiCore',type(None)]

	@classmethod
	def get_fields(cls):
		# type: () -> Dict[str, str]
		return {x.name: x.validator.type[0] for x in attr.fields(cls)}

	def get_not_none_values_as_dict(self):
		# type: () -> Dict[str, Any]
		return {k: v for k, v in self.__dict__.items() if v is not None and "_" not in k}

	def __sub__(self, other):
		# type: (AzureObject) -> AzureObject
		# TODO: could use the get_not_none_values_as_dict method?
		return other.__class__(**{k: v for k, v in other.__dict__.items() if self.__dict__[k] != v and "_" not in k})

	def set_core(self, core):
		# type: (MSGraphApiCore) -> None
		self._core = core

	def _update_from_dict(self, data):
		# type: (Dict[str, Any]) -> None
		for k, v in data.items():
			if hasattr(self, k):
				setattr(self, k, v)

	# TODO: check if it's the place/class for this static method
	@staticmethod
	def wait_for_operation(core, response):
		# type: (MSGraphApiCore, Dict[str, Any]) -> None
		if "operations" in response.get("Location", ""):
			print(response.get("Location"))
			while True:
				try:
					r = core.wait_for_operation(response.get("Location"))
				except MSGraphError:
					time.sleep(10)
					continue
				if r.get("status") == 'succeeded':
					break
				time.sleep(30)

	@abstractmethod
	def create(self):
		# type: () -> None
		""""""

	@abstractmethod
	def delete(self):
		# type: () -> None
		""""""

	@abstractmethod
	def update(self, other):
		# type: ('AzureObject') -> None
		""""""

	@abstractmethod
	def deactivate(self, rename=False):
		# type: (bool) -> None
		""""""

	@abstractmethod
	def reactivate(self):
		# type: () -> None
		""""""

	@classmethod
	@abstractmethod
	def get(cls, core, oid):
		# type: (MSGraphApiCore, str) -> 'AzureObject'
		""""""

	@staticmethod
	@abstractmethod
	def list(core):
		# type: (MSGraphApiCore) -> List['AzureObject']
		""""""

	def add_license(self, subs_sku, deactivated_plans=None):
		# type: (SubscriptionAzure, List) -> None
		""""""
		try:
			self._core.add_license(self.id, subs_sku.skuId, deactivated_plans)
		except MSGraphError as exc:
			reraise(AddLicenseError, AddLicenseError(str(exc), self.id, subs_sku.skuId, exc), sys.exc_info()[2])

	def remove_license(self, subs_sku):
		# type: (SubscriptionAzure) -> None
		""""""
		self._core.remove_license(self.id, subs_sku.skuId)

	def member_of(self):
		# type: () -> List[GroupAzure]
		""""""
		groups_response = self._core.member_of(self.id)
		groups = []
		for group_response in groups_response["value"]:
			group = GroupAzure()
			group._update_from_dict(group_response)
			group.set_core(self._core)
			groups.append(group)
		return groups

@attr.s
class UserAzure(AzureObject):
	"""
	https://docs.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0
	Represents a User in Azure AD.
	The valid Azure User attributes are defined in the class attributes.
	Methods:
		- create: creates a new user in Azure AD
		- delete: deletes a user in Azure AD
		- update: updates a user in Azure AD
		- deactivate: deactivates a user in Azure AD
		- reactivate: reactivates a user in Azure AD
		- member_of: returns the groups the user is a member of
		- get: returns an Azure User got by it's id from Azure AD (class method)
		- reset_password: resets the user's password in Azure AD
		- list: returns a list of all users in Azure AD (static)
		- invalidate_all_tokens: invalidates all tokens for the user in Azure AD
	"""
	aboutMe = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	accountEnabled = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	ageGroup = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	assignedPlans = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	birthday = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	businessPhones = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	calendarGroups = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	calendars = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	city = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	companyName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	consentProvidedForMinor = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	contactFolders = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	contacts = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	country = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	createdObjects = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	creationType = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	department = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	directReports = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	drives = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	employeeHireDate = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	employeeId = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	employeeOrgData = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, str]
	employeeType = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	faxNumber = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	givenName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	hireDate = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	identities = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	imAddresses = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	inferenceClassification = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, str]
	interests = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	isResourceAccount = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	jobTitle = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	lastPasswordChangeDateTime = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	legalAgeGroupClassification = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	licenseAssignmentStates = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	mailFolders = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	mailboxSettings = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, str]
	manager = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, str]
	messages = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	mobilePhone = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	mySite = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	officeLocation = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	onPremisesDistinguishedName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	onPremisesDomainName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	onPremisesExtensionAttributes = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, str]
	onPremisesImmutableId = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	onPremisesSamAccountName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	onPremisesUserPrincipalName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	otherMails = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	outlook = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, str]
	ownedDevices = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	ownedObjects = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	passwordPolicies = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	passwordProfile = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, str]
	pastProjects = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	postalCode = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	preferredName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	provisionedPlans = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	registeredDevices = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	responsibilities = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	schools = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	showInAddressList = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	signInSessionsValidFromDateTime = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	skills = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	state = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	streetAddress = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	surname = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	usageLocation = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	userPrincipalName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	userType = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str

	def create(self):
		# type: () -> None
		""""""
		response = self._core.add_user(self.get_not_none_values_as_dict())
		self._update_from_dict(response)

	def create_or_modify(self):
		# type: () -> None
		""""""
		try:
			response = self._core.add_user(self.get_not_none_values_as_dict())
		except MSGraphError as exc:
			if hasattr(exc.response, "json"):
				# TODO move to core_exception
				if "error" in exc.response.json() and "details" in exc.response.json()["error"]:
					details = exc.response.json()["error"]["details"]
					for d in details:
						if d.get("code") == "ObjectConflict" and d.get("target") == "userPrincipalName":
							# The user already exists, so we need to modify it
							# get the user from azure by its
							user_azure = self.get(self._core, self.userPrincipalName)
							self.id = user_azure.id
							# update the azure user with the new values
							user_azure.update(self)
							return
				# Only if the user fails to be created and don't exist in azure either
				raise
		self._update_from_dict(response)
	# TODO update user with the response ??

	def delete(self):
		# type: () -> None
		""""""
		# self._core.delete_user(self.id)
		self.deactivate(rename=True)

	# TODO update user with the response ??

	def update(self, other):
		# type: ('AzureObject') -> None
		""""""
		data = (self - other).get_not_none_values_as_dict()
		can_only_be_created_not_modified = ["mobile", "passwordProfile"]
		for attrib in can_only_be_created_not_modified:
			if attrib in data:
				# read text at beginning delete_user()
				del data[attrib]
		self._core.modify_user(self.id, data)
		self._update_from_dict(data)

	# TODO update user with the response ??

	def deactivate(self, rename=False):
		# type: (bool) -> None
		""""""
		modifications_user = UserAzure(assignedLicenses=[], accountEnabled=False, otherMails=[])
		if rename:
			if re.match(r'^ZZZ_deleted_.+_.+', self.userPrincipalName):
				# this shouldn't happen
				# logger.warn("User %r (%s) already deactivated, ignoring.", self.userPrincipalName, self._core.adconnection_alias)
				pass
			else:
				modifications_user.displayName = delete_name_pattern.format(time=time.time(), orig=self.displayName)
				modifications_user.mailNickname = delete_name_pattern.format(time=time.time(), orig=self.mailNickname)
				modifications_user.userPrincipalName = delete_name_pattern.format(time=time.time(), orig=self.userPrincipalName)
		data = modifications_user.get_not_none_values_as_dict()
		self._core.modify_user(self.id, data)
		self._update_from_dict(data)
		# TODO check if the assignedLicenses is clean
		groups = self._core.member_of(self.id)
		for group in groups["value"]:
			self._core.remove_group_member(group["id"], self.id)
		for _license in self.assignedLicenses:
			self.remove_license(_license["skuId"])

	def reactivate(self, rename=False):
		# type: (bool) -> None
		""""""
		raise NotImplementedError()

	@classmethod
	def get(cls, core, oid):
		# type: (MSGraphApiCore, str) -> 'AzureObject'
		""""""
		user = cls()
		attrs = [x.name for x in attr.fields(cls) if x.name not in ["mailboxSettings"]]
		response = core.get_user(oid, selection=",".join(attrs))
		user._update_from_dict(response)
		user.set_core(core)
		return user

	def reset_password(self):
		# type: () -> None
		# self._core.reset_password(self.id, self.passwordProfile["password"], create_random_pw())
		self.update(UserAzure(passwordProfile=dict(password=create_random_pw(), forceChangePasswordNextSignIn=False)))
		# reset the user password to a random string, to reset the attribute when
		# the last userpassword change happened, pwdLastSet. Bug #49699
		# "Either delegated scope User.ReadWrite.All or Directory.AccessAsUser.All is required to reset a user's password."
		"""TODO"""

	@staticmethod
	def list(core):
		# type: (MSGraphApiCore) -> List['UserAzure']
		""""""
		users_response = core.list_users()
		users_value = users_response.get("value", [])
		if users_value:
			users = [UserAzure(**x) for x in users_value]
			[x.set_core(core) for x in users]
			return users

	def invalidate_all_tokens(self):
		# type: () -> None
		self._core.invalidate_all_tokens_for_user(self.id)


@attr.s
class GroupAzure(AzureObject):
	"""
	https://docs.microsoft.com/en-us/graph/api/resources/group?view=graph-rest-1.0
	Represents a Group in Azure AD.
	The valid Azure Group attributes are defined in the class attributes.
	Methods:
		- create: create a new group in Azure AD
		- delete: delete a group in Azure AD
		- update: update a group in Azure AD
		- deactivate: deactivate a group in Azure AD
		- reactivate: reactivate a group in Azure AD
		- get: get a group from Azure AD by its id (class method)
		- add_member: add a member to a group in Azure AD
		- add_owner: add an owner to a group in Azure AD
		- remove_owner: remove an owner from a group in
		- list_members: list the members of a group in Azure AD
		- list_owners: list the owners of a group in Azure AD
		- remove_member: remove a member from a group in Azure AD
		- list: list all the groups in Azure AD (static)
	"""
	acceptedSenders = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	allowExternalSenders = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	autoSubscribeNewMembers = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	classification = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	conversations = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	createdOnBehalfOf = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, str]
	description = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	groupTypes = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	hasMembersWithLicenseErrors = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	hideFromAddressLists = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	hideFromOutlookClients = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	isAssignableRole = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	isSubscribedByMail = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	licenseProcessingState = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	mailEnabled = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	members = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	membersWithLicenseErrors = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	owners = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	rejectedSenders = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	renewedDateTime = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	resourceBehaviorOptions = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	resourceProvisioningOptions = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[str]
	securityEnabled = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	securityIdentifier = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	sites = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	threads = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List[Dict[str, str]]
	unseenCount = attr.ib(validator=attr.validators.instance_of((int, type(None))), default=None)  # None
	visibility = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	deletedDateTime = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	creationOptions = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  #: List
	expirationDateTime = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	isAssignableToRole = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	membershipRule = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	membershipRuleProcessingState = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	onPremisesDomainName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	onPremisesNetBiosName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	onPremisesSamAccountName = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	onPremisesSecurityIdentifier = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	onPremisesSyncEnabled = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  #: bool
	preferredDataLocation = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str
	theme = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  #: str

	def create(self):
		# type: () -> None
		""""""
		response = self._core.create_group(self.get_not_none_values_as_dict())
		self._update_from_dict(response)

	def create_or_modify(self):
		# type: () -> None
		""""""
		if not self.exist():
			response = self._core.create_group(self.get_not_none_values_as_dict())
			self._update_from_dict(response)
		else:
			self._core.modify_group(self.id, self.get_not_none_values_as_dict())

	@classmethod
	def get_by_name(cls, core, displayName):
		# type: (MSGraphApiCore, str) -> Optional[GroupAzure]
		response = core.list_groups("$filter=displayName eq '{value}'".format(value=displayName))
		if response["value"]:
			group = cls()
			group._update_from_dict(response["value"][0])
			group.set_core(core)
			return group
		return None

	# TODO update user with the response ??
	def exist(self):
		# type: () -> bool
		response = self._core.list_groups("$filter=displayName eq '{value}'".format(value=self.displayName))
		if response["value"]:
			self.id = response["value"][0]["id"]
			return True
		return False

	def delete(self):
		# type: () -> None
		""""""
		# TODO if the team exist it should be archive first.
		self._core.delete_group(self.id)

	def update(self, other):
		# type: ("AzureObject") -> None
		""""""
		data = (self - other).get_not_none_values_as_dict()
		response = self._core.modify_group(self.id, data)
		self._update_from_dict(response)

	def deactivate(self, rename=False):
		# type: (bool) -> None
		""""""
		name = "ZZZ_deleted_{time}_{orig}".format(time=time.time(), orig=self.displayName)
		data = dict(displayName=name,
					description="deleted group",
					mailEnabled=False, mailNickname=name.replace(" ", "_-_"), )
		self._core.modify_group(self.id, data)
		self._update_from_dict(data)

	def reactivate(self):
		# type: () -> None
		""""""
		raise NotImplementedError()

	@classmethod
	def get(cls, core, oid):
		# type: (MSGraphApiCore, str) -> 'AzureObject'
		""""""
		attrs = [x.name for x in attr.fields(cls) if x.name not in ["hasMembersWithLicenseErrors", "allowExternalSenders", "autoSubscribeNewMembers", "hideFromAddressLists", "hideFromOutlookClients", "isSubscribedByMail", "unseenCount"]]
		response = core.get_group(group_id=oid, selection=",".join(attrs))
		group = cls()
		group._update_from_dict(response)
		group.set_core(core)
		return group

	def add_member(self, object_id):
		# type: (str) -> None
		""""""
		self._core.add_group_member(self.id, object_id)

	def add_members(self, object_ids):
		# type: (List[str]) -> None
		""""""
		self._core.add_group_members(self.id, object_ids)

	def add_owner(self, owner_id, async_task=False):
		# type: (str, bool) -> Optional[MSGraphCoreTask]
		""""""
		if async_task:
			return MSGraphCoreTask(self._core.account.alias, "add_group_owner", (self.id, owner_id))
		self._core.add_group_owner(self.id, owner_id)

	def remove_owner(self, owner_id):
		# type: () -> None
		""""""
		self._core.remove_group_owner(self.id, owner_id)

	def list_members(self):
		# type: () -> List[Union[UserAzure, GroupAzure]]
		""""""
		members_response = self._core.list_group_members(self.id)
		members = []
		for member_response in members_response["value"]:
			if "user" in member_response['@odata.type']:
				member = UserAzure()
			elif "group" in member_response['@odata.type']:
				member = GroupAzure()
			else:
				member = AzureObject()
				member_response = dict(id=member_response["id"])
			member._update_from_dict(member_response)
			member.set_core(self._core)
			members.append(member)
		return members

	def list_members_id(self):
		# type: () -> List[str]
		""""""
		members_response = self._core.list_group_members(self.id, filter="$select=id")
		return [x["id"] for x in members_response["value"]]

	def remove_direct_members(self):
		# type: () -> None
		""""""
		for member_id in self.list_members_id():
			self.remove_member(member_id)

	def list_owners(self):
		# type: () -> List[UserAzure]
		users_response = self._core.list_group_owners(self.id)
		users = []
		for user_response in users_response["value"]:
			user = UserAzure()
			user._update_from_dict(user_response)
			user.set_core(self._core)
			users.append(user)
		return users

	def remove_member(self, user_id):
		# type: (str) -> None
		""""""
		self._core.remove_group_member(group_id=self.id, object_id=user_id)

	@staticmethod
	def list(core):
		# type: (MSGraphApiCore) -> List['GroupAzure']
		""""""
		groups_response = core.list_groups()
		groups_value = groups_response.get("value", [])
		if groups_value:
			print(groups_value[0])
			groups = [GroupAzure(**x) for x in groups_value]
			[x.set_core(core) for x in groups]
			return groups

	def is_delete(self):
		# type: () -> bool
		return self.mailNickname.startswith("ZZZ_deleted_") if self.mailNickname else False

@attr.s
class TeamAzure(AzureObject):
	"""
	https://docs.microsoft.com/en-us/graph/api/resources/team?view=graph-rest-1.0
	Represents a Team in Azure AD.
	The valid Azure Team attributes are defined in the class attributes.
	Methods:
		- set_owner: set the owner of the team in Azure AD.
		- create: create the team in Azure AD.
		- wait_for_team: wait for the team to be created in Azure AD.
		- create_from_group: create the team from an existing group in Azure AD.
		- delete: delete the team in Azure AD.
		- update: update the team in Azure AD.
		- deactivate: deactivate the team in Azure AD.
		- reactivate: reactivate the team in Azure AD.
		- add_member: add a member to the team in Azure AD.
		- delete_member: delete a member from the team in Azure AD.
		- list_team_members: list the members of the team in Azure AD.
		- list: list the teams in Azure AD (static).
		- get: get the team in Azure AD (class method).
	"""
	description = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	internalId = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	classification = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	specialization = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	visibility = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	webUrl = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	isArchived = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	isMembershipLimitedToOwners = attr.ib(validator=attr.validators.instance_of((bool, type(None))), default=None)  # bool
	discoverySettings = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, bool]
	summary = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	memberSettings = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, bool]
	guestSettings = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, bool]
	messagingSettings = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, bool]
	funSettings = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict[str, bool]
	_owner_id = None  # type: Union[type(None), str]
	_content_location = None  # type: Union[type(None), str]

	def set_owner(self, owner_id):
		# type: (str) -> None
		self._owner_id = owner_id

	def create(self):
		# type: () -> None
		""""""
		if hasattr(self, "_owner_id") and self._owner_id:
			response = self._core.create_team(name=self.displayName, owner=self._owner_id, description=self.description)
			TeamAzure.wait_for_operation(self._core, response)
			self._content_location = response["Content-Location"]
		else:
			raise Exception("Set owner before create the team")

	def wait_for_team(self):
		# type: () -> None
		if self._content_location:
			time_slept = 0
			while True:
				try:
					response = self._core.wait_for_operation(self._content_location)
					self._update_from_dict(response)
					break
				except MSGraphError as e:
					time.sleep(10)
					time_slept += 10
					if time_slept >= 180:
						raise e
		elif self.id:
			time_slept = 0
			while True:
				try:
					response = self._core.get_team(self.id)
					self._update_from_dict(response)
					break
				except MSGraphError as e:
					time.sleep(10)
					time_slept += 10
					if time_slept >= 180:
						raise e

	@staticmethod
	def create_from_group_async(alias, group_id, sub_tacks):
		# type: (str, str, List[MSGraphCoreTask]) -> MSGraphCoreTask
		return MSGraphCoreTask(alias, "create_team_from_group", dict(object_id=group_id), sub_tasks=sub_tacks)

	@classmethod
	def create_from_group(cls, core, group_id):
		# type: (MSGraphApiCore, str) -> TeamAzure
		time_slept = 0
		while True:
			try:
				core.create_team_from_group(object_id=group_id)
				# TeamAzure.wait_for_operation(core, response)
				break
			except MSGraphError as e:
				time.sleep(10)
				time_slept += 10
				if time_slept >= 180:
					raise e
		team = cls(id=group_id)
		team.set_core(core)
		return team

	def delete(self):
		# type: () -> None
		""""""
		data = dict(displayName="ZZZ_deleted_{time}_{orig}".format(time=time.time(), orig=self.displayName), description="deleted group")
		response = self._core.modify_team(self.id, data)
		TeamAzure.wait_for_operation(self._core, response)

		self._update_from_dict(data)
		self._core.archive_team(self.id)
		# TeamAzure.wait_for_operation(self._core, response)
		self.isArchived = True

	def update(self, other):
		# type: (AzureObject) -> None
		""""""
		data = (self - other).get_not_none_values_as_dict()
		response = self._core.modify_team(self.id, data)
		TeamAzure.wait_for_operation(self._core, response)
		self._update_from_dict(response)

	def deactivate(self, rename=False):
		# type: (bool) -> None
		""""""
		response = self._core.archive_team(self.id)
		TeamAzure.wait_for_operation(self._core, response)

	def reactivate(self):
		# type: () -> None
		""""""
		response = self._core.unarchive_team(self.id)
		TeamAzure.wait_for_operation(self._core, response)

	def add_member(self, user_id):
		# type: (str) -> Dict[str, Any]
		""""""
		response = self._core.add_team_member(self.id, user_id)
		TeamAzure.wait_for_operation(self._core, response)
		return response

	def delete_member(self, membership_id):
		# type: (str) -> None
		"""
		:param membership_id: this is the id returned when member is added or list
		"""
		response = self._core.remove_team_member(self.id, membership_id=membership_id)
		TeamAzure.wait_for_operation(self._core, response)

	def list_team_members(self):
		# type: () -> List[UserAzure]
		""""""
		response = self._core.list_team_members(self.id)
		TeamAzure.wait_for_operation(self._core, response)
		users = []
		for user_response in response["value"]:
			user = UserAzure(id=user_response["userId"], displayName=user_response["displayName"])
			user.set_core(self._core)
			users.append(user)
		return users

	@staticmethod
	def list(core):
		# type: (MSGraphApiCore) -> List['TeamAzure']
		""""""
		response = core.list_teams(paging=True)
		TeamAzure.wait_for_operation(core, response)
		teams = []
		for team_dict in response["value"]:
			team = TeamAzure()
			team._update_from_dict(team_dict)
			team.set_core(core)
			teams.append(team)
		return teams

	@classmethod
	def get(cls, core, oid):
		# type: (MSGraphApiCore, str) -> AzureObject
		""""""
		response = core.get_team(group_id=oid)
		TeamAzure.wait_for_operation(core, response)
		team = cls()
		team._update_from_dict(response)
		team.set_core(core)
		return team


@attr.s
class SubscriptionAzure(AzureObject):
	"""
	https://docs.microsoft.com/en-us/graph/api/resources/subscription?view=graph-rest-1.0
	Represents a Subscription in Azure AD.
	The valid Azure Subscription attributes are defined in the class attributes.
	Methods:
		- get: get a subscription from Azure AD by its id
		- list: list all available subscriptions in Azure AD
		- get_enabled: get the enabled subscriptions in Azure AD
		- has_free_seats: check if the subscription has free seats
		- get_plans_names: get the plan names of the subscription
		- get_plans_id_from_names: get the plan ids for a list of plan names
	"""
	appliesTo = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	capabilityStatus = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str
	consumedUnits = attr.ib(validator=attr.validators.instance_of((int, type(None))), default=None)  # int
	prepaidUnits = attr.ib(validator=attr.validators.instance_of((Dict, type(None))), default=None)  # Dict
	servicePlans = attr.ib(validator=attr.validators.instance_of((List, type(None))), default=None)  # List
	skuId = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str,
	skuPartNumber = attr.ib(validator=attr.validators.instance_of((str, type(None))), default=None)  # str

	def create(self):
		# type: () -> None
		""""""
		raise NotImplementedError

	def deactivate(self, rename=False):
		# type: () -> None
		""""""
		raise NotImplementedError

	def delete(self):
		# type: () -> None
		""""""
		raise NotImplementedError

	def reactivate(self):
		# type: () -> None
		""""""
		raise NotImplementedError

	def update(self, other):
		# type: (SubscriptionAzure) -> None
		""""""
		raise NotImplementedError

	@classmethod
	def get(cls, core, oid):
		# type: (MSGraphApiCore,str) -> 'SubscriptionAzure'
		""""""
		subscription_response = core.get_subscriptionSku(subs_sku_id=oid)
		subscription_response.pop("@odata.context")
		return cls(**subscription_response)

	@staticmethod
	def list(core):
		# type: (MSGraphApiCore) -> List['SubscriptionAzure']
		""""""
		subscriptions_response = core.list_subscriptions()
		subscriptions = [SubscriptionAzure(**subscription) for subscription in subscriptions_response["value"]]
		[x.set_core(core) for x in subscriptions]
		return subscriptions

	@staticmethod
	def get_enabled(core, service_plan_names):
		# type: (MSGraphApiCore, List[str]) -> List['SubscriptionAzure']
		"""TODO"""
		subscriptions_response = core.list_subscriptions()
		# subscriptions = [SubscriptionAzure(**subscription) for subscription in subscriptions_response["value"] if subscription["appliesTo"] == "User" and subscription["capabilityStatus"] == "Enabled" and any([plan["servicePlanName"] in service_plan_names for plan in subscription["servicePlans"]])]
		# [x.set_core(core) for x in subscriptions]
		subscriptions = list()
		for subscription in subscriptions_response["value"]:
			if subscription["appliesTo"] == "User" and subscription["capabilityStatus"] == "Enabled":
				for plan in subscription["servicePlans"]:
					if plan["servicePlanName"] in service_plan_names:
						# found an office plan
						sub_sku = SubscriptionAzure(**subscription)
						sub_sku.set_core(core)
						subscriptions.append(sub_sku)
		# 				break
		return subscriptions

	def has_free_seats(self):
		# type: () -> bool
		""""""
		return self.prepaidUnits["enabled"] > self.consumedUnits

	def get_plans_names(self):
		# type: () -> List
		""""""
		return [plan['servicePlanName'] for plan in self.servicePlans]


	def get_plans_id_from_names(self, plan_names):
		# type: (List) -> List
		""""""
		return [plan['servicePlanId'] for plan in self.servicePlans if plan['servicePlanName'] in plan_names]
