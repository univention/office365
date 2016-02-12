#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle Azure API calls
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

import json
import urllib
import uuid
import requests
import collections
import time
import re
from operator import itemgetter

from univention.office365.azure_auth import AzureAuth, AzureError, log_a, log_e, log_ex, log_p, resource_url


azure_params = {"api-version": "1.6"}
azure_attribute_types = dict(
	accountEnabled=bool,
	addLicenses=list,
	assignedLicenses=list,
	city=unicode,
	country=unicode,
	department=unicode,
	description=unicode,
	displayName=unicode,
	facsimileTelephoneNumber=unicode,
	forceChangePasswordNextLogin=bool,
	givenName=unicode,
	immutableId=unicode,
	jobTitle=unicode,
	mail=unicode,
	mailEnabled=bool,
	mailNickname=unicode,
	mobile=unicode,
	otherMails=list,
	passwordPolicies=unicode,
	passwordProfile=dict,
	password=unicode,
	physicalDeliveryOfficeName=unicode,
	postalCode=unicode,
	preferredLanguage=unicode,
	removeLicenses=list,
	securityEnabled=bool,
	state=unicode,
	streetAddress=unicode,
	surname=unicode,
	telephoneNumber=unicode,
	thumbnailPhoto=bytes,
	url=str,
	usageLocation=unicode,
	userPrincipalName=unicode,
	userType=unicode
)
servicePlanId_SHAREPOINTWAC = "e95bec33-7c88-4a70-8e19-b10bd9d0c014"  # Office Web Apps


def _get_azure_uris(tenant_id):
	graph_base_url = "{0}/{1}".format(resource_url, tenant_id)

	return dict(
		directoryObjects="%s/directoryObjects/{object_id}" % graph_base_url,
		users="%s/users?{params}" % graph_base_url,
		user="%s/users/{object_id}?{params}" % graph_base_url,
		user_assign_license="%s/users/{user_id}/assignLicense?{params}" % graph_base_url,
		user_direct_groups="%s/users/{user_id}/$links/memberOf?{params}" % graph_base_url,
		getMemberObjects="%s/{resource_collection}/{resource_id}/getMemberObjects?{params}" % graph_base_url,
		getMemberGroups="%s/{resource_collection}/{resource_id}/getMemberGroups?{params}" % graph_base_url,
		getObjectsByObjectIds="%s/getObjectsByObjectIds?{params}" % graph_base_url,
		groups="%s/groups?{params}" % graph_base_url,
		group="%s/groups/{object_id}?{params}" % graph_base_url,
		group_members="%s/groups/{group_id}/$links/members?{params}" % graph_base_url,
		group_member="%s/groups/{group_id}/$links/members/{member_id}?{params}" % graph_base_url,
		subscriptions="%s/subscribedSkus?{params}" % graph_base_url,
		domains="%s/domains?{params}" % graph_base_url,
		domain="%s/domains({domain_name})?{params}" % graph_base_url,
		tenantDetails="%s/tenantDetails?{params}" % graph_base_url,
	)


class ApiError(AzureError):
	def __init__(self, response):
		msg = "Communication error."
		if hasattr(response, "json"):
			j = response.json
			if callable(j):  # requests version compatibility
				j = j()
			msg = j["odata.error"]["message"]["value"]
			self.json = j
		self.response = response
		log_e(msg)
		super(ApiError, self).__init__(msg)


class ResourceNotFoundError(ApiError):
	pass


class UnkownTypeError(AzureError):
	pass


class AzureHandler(object):
	def __init__(self, listener, name):
		self.listener = listener
		self.name = name
		self.auth = AzureAuth(listener, name)
		self.uris = _get_azure_uris(self.auth.tenant_id)

	def call_api(self, method, url, data=None, retry=0):
		request_id = str(uuid.uuid4())
		headers = {
			"User-Agent": "ucs-office365/1.0",
			"Authorization": "Bearer {token}",
			"Accept": "application/json",
			"client-request-id": request_id,
			"return-client-request-id": "true"}

		response_json = None
		access_token = self.auth.get_access_token()
		headers["Authorization"] = "Bearer {}".format(access_token)

		data = self._prepare_data(data)
		# hide password
		msg = self._fprints_hide_pw(data, "AzureHandler.call_api() %s %s data: {data}" % (method.upper(), url))
		log_a(msg)

		args = dict(url=url, headers=headers, verify=True)
		if method.upper() in ["PATCH", "POST"]:
			headers["Content-Type"] = "application/json"
			args["data"] = json.dumps(data)

		requests_func = getattr(requests, method.lower())
		response = requests_func(**args)

		if response is not None:
			try:
				response_json = response.json
				if callable(response_json):  # requests version compatibility
					response_json = response_json()
			except (TypeError, ValueError):
				if method.upper() in ["DELETE", "PATCH", "PUT"]:
					# no response expected
					pass
				elif method.upper() == "POST" and "members" in url:
					# no response expected (add_objects_to_group())
					pass
				else:
					log_ex("AzureHandler.call_api() response is not JSON. response.__dict__: {}".format(response.__dict__))
					raise ApiError(response)

			log_a("AzureHandler.call_api() status: {} ({}){}".format(
				response.status_code,
				"OK" if 200 <= response.status_code <= 299 else "FAIL",
				" Code: {}".format(response_json["odata.error"]["code"]) if response_json and "odata.error" in response_json else ""))

			if not (200 <= response.status_code <= 299):
				if response.status_code == 404 and response_json["odata.error"]["code"] == "Request_ResourceNotFound":
					raise ResourceNotFoundError(response)
				elif 500 <= response.status_code <= 599:
					# server error
					if retry > 0:
						raise ApiError(response)
					else:
						log_e("AzureHandler.call_api() Server error. Azure said: '{}'. Will sleep 10s and then retry one time.".format(response_json["odata.error"]["message"]["value"]))
						time.sleep(10)
						self.call_api(method, url, data=data, retry=retry+1)
				else:
					raise ApiError(response)
		else:
			log_e("AzureHandler.call_api() response is None")
			raise ApiError("Response is None")
		return response_json or response

	def _list_objects(self, object_type, object_id=None, ofilter=None, params_extra=None, url_extra=None):
		assert object_type in ["user", "group", "subscription", "domain", "tenantDetail"], 'Unsupported object type.'
		if params_extra:
			assert isinstance(params_extra, dict)

		params = dict(**azure_params)
		if params_extra:
			params.update(params_extra)
		if ofilter:
			params["$filter"] = ofilter
		params = urllib.urlencode(params)
		if object_id:
			assert type(object_id) == str, 'The ObjectId must be a string of form "893801ca-e843-49b7-9f64-7a4590b72769".'
			url = self.uris[object_type].format(
				params=params,
				object_id=object_id,
				**url_extra if url_extra else {})
		else:
			url = self.uris[object_type + "s"].format(params=params)
		return self.call_api("GET", url)

	def list_users(self, objectid=None, ofilter=None):
		return self._list_objects(object_type="user", object_id=objectid, ofilter=ofilter)

	def get_users_direct_groups(self, user_id):
		params = urllib.urlencode(azure_params)
		url = self.uris["user_direct_groups"].format(user_id=user_id, params=params)
		return self.call_api("GET", url)

	def list_groups(self, objectid=None, ofilter=None):
		return self._list_objects(object_type="group", object_id=objectid, ofilter=ofilter)

	def _create_object(self, object_type, attributes, obj_id):
		"""
		if object exists, it will be modified instead
		"""
		assert object_type in ["user", "group"], 'Currently only "user" and "group" supported.'
		assert type(attributes) == dict
		assert "displayName" in attributes
		assert type(obj_id) == dict
		assert "key" in obj_id
		assert "value" in obj_id

		# hide password
		msg = self._fprints_hide_pw(attributes, "AzureHandler._create_object() Creating %s with properties: {data}" % object_type)
		log_p(msg)

		obj = self._list_objects(object_type=object_type, ofilter="{key} eq '{value}'".format(**obj_id))
		if obj["value"]:
			log_p("AzureHandler._create_object() {} '{}' exists, modifying it.".format(
					object_type,
					obj["value"][0]["displayName"]))

			return self._modify_objects(
					object_type=object_type,
					object_id=obj["value"][0]["objectId"],
					modifications=attributes)
		else:
			params = urllib.urlencode(azure_params)
			url = self.uris[object_type + "s"].format(params=params)
			return self.call_api("POST", url, attributes)

	def create_user(self, attributes):
		"""
		if user exists, it will be modified instead
		"""
		return self._create_object(
				object_type="user",
				attributes=attributes,
				obj_id={"key": "immutableId", "value": attributes["immutableId"]})

	def create_group(self, name, description=None):
		"""
		if group exists, it will be modified instead
		"""
		attributes = dict(
			description=description,
			displayName=name,
			mailEnabled=False,
			mailNickname=name.replace(" ", "_-_"),
			securityEnabled=True
		)
		return self._create_object(
				object_type="group",
				attributes=attributes,
				obj_id={"key": "displayName", "value": name})

	def _modify_objects(self, object_type, object_id, modifications):
		assert object_type in ["user", "group"], 'Currently only "user" and "group" supported.'
		assert type(object_id) == str, "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."
		assert type(modifications) == dict, "Please supply a dict of attr->value to change."

		can_only_be_created_not_modified = ["mobile", "passwordProfile"]
		for attrib in can_only_be_created_not_modified:
			if attrib in modifications:
				# read text at beginning delete_user()
				del modifications[attrib]
				log_e("AzureHandler._modify_objects() Modifying '{attrib}' is currently not supported. '{attrib}' removed from modification list.".format(attrib=attrib))
		log_p("AzureHandler._modify_objects() Modifying {} with object_id {} and modifications {}...".format(object_type, object_id, modifications))

		params = urllib.urlencode(azure_params)
		url = self.uris[object_type].format(object_id=object_id, params=params)
		return self.call_api("PATCH", url, modifications)

	def modify_user(self, object_id, modifications):
		return self._modify_objects(object_type="user", object_id=object_id, modifications=modifications)

	def modify_group(self, object_id, modifications):
		if "uniqueMember" in modifications:
			raise RuntimeError("Attribute uniqueMember must be dealt with in listener.")
		return self._modify_objects(object_type="group", object_id=object_id, modifications=modifications)

	def _delete_objects(self, object_type, object_id):
		assert object_type in ["user", "group"], 'Currently only "user" and "group" supported.'
		assert type(object_id) == str, "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."
		log_p("AzureHandler._delete_objects() Deleting {} with object_id {}...".format(object_type, object_id))

		params = urllib.urlencode(azure_params)
		url = self.uris[object_type].format(object_id=object_id, params=params)
		try:
			return self.call_api("DELETE", url)
		except ResourceNotFoundError as exc:
			log_e("Object '{}' didn't exist: {}".format(object_id, exc))
			return

	def delete_user(self, object_id):
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
		# So for now use deactivte_user() instead of _delete_objects().
		#

		# return self._delete_objects(object_type="user", object_id=object_id)
		return self.deactivate_user(object_id, rename=True)

	def delete_group(self, object_id):
		# see delete_user()
		# return self._delete_objects(object_type="group", object_id=object_id)
		return self.deactivate_group(object_id)

	def _member_of_(self, obj, object_id):
		"""
		Transitive versions (incl nested groups)
		"""
		log_p("AzureHandler._member_of_() Querying memberOf {} for user with object_id {}...".format(obj, object_id))
		assert type(object_id) == str, "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."

		data = {"securityEnabledOnly": True}
		params = urllib.urlencode(azure_params)
		if obj == "groups":
			url = self.uris["getMemberGroups"].format(resource_collection="users", resource_id=object_id, params=params)
		else:
			url = self.uris["getMemberObjects"].format(resource_collection="users", resource_id=object_id, params=params)
		return self.call_api("POST", url, data)

	def member_of_groups(self, object_id):
		return self._member_of_("groups", object_id)

	def member_of_objects(self, object_id):
		return self._member_of_("objects", object_id)

	def resolve_object_ids(self, object_ids, object_types=None):
		assert type(object_ids) == list, "Parameter object_ids must be a list of object IDs."

		data = {"objectIds": object_ids}
		params = urllib.urlencode(azure_params)
		url = self.uris["getObjectsByObjectIds"].format(params=params)
		return self.call_api("POST", url, data)

	def get_groups_direct_members(self, group_id):
		assert type(group_id) in [str, unicode], "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."

		params = urllib.urlencode(azure_params)
		url = self.uris["group_members"].format(group_id=group_id, params=params)
		return self.call_api("GET", url)

	def add_objects_to_group(self, group_id, object_ids):
		assert type(group_id) == str, "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."
		assert type(object_ids) == list, "object_ids must be a non-empty list of objectID strings."
		assert len(object_ids) > 0, "object_ids must be a non-empty list of objectID strings."
		log_p("AzureHandler.add_objects_to_group() Adding objects {} to group {}...".format(object_ids, group_id))

		# While the Graph API clearly states that multiple objects can be added
		# at once to a group that is no entirely true, as the usual API syntax
		# does not allow it. In the end a MS employee found out, that a OAuth
		# Batch request has to be created and then still only 5 objects can be
		# added at once (https://social.msdn.microsoft.com/Forums/azure/en-US/04113864-51af-4d46-8b13-725e4120433b/graphi-api-how-to-add-many-members-to-a-group).
		# The added complexity is entirely out of proportion for the benefit,
		# so here comes a loop instead.
		for object_id in object_ids:
			if not object_id:
				log_e("AzureHandler.add_objects_to_group() empty object_id should be added to {}, ignoring.".format(group_id))
				continue
			# Check if object is already there, because adding it again leads
			# to an error: "One or more added object references already exist
			# for the following modified properties: 'members'."
			dir_obj_url = self.uris["directoryObjects"].format(object_id=object_ids[0])
			objs = {"url": dir_obj_url}
			members = self.get_groups_direct_members(group_id)
			object_ids_already_in_azure = self.directory_object_urls_to_object_ids(members["value"])
			if object_id in object_ids_already_in_azure:
				log_a("AzureHandler.add_objects_to_group() object {} already in group.".format(object_ids[0]))
				continue
			params = urllib.urlencode(azure_params)
			url = self.uris["group_members"].format(group_id=group_id, params=params)
			self.call_api("POST", url, data=objs)

	def delete_group_member(self, group_id, member_id):
		log_p("AzureHandler.delete_group_member() Removing member {} from group {}...".format(member_id, group_id))
		params = urllib.urlencode(azure_params)
		url = self.uris["group_member"].format(group_id=group_id, member_id=member_id, params=params)
		# TODO: delete group if empty... but not from here...
		try:
			return self.call_api("DELETE", url)
		except ApiError as exc:
			log_ex("ApiError deleting a group member")
			log_e("ae.__dict__={}".format(exc.__dict__))
			if hasattr(exc, "json"):
				log_e("ae.json={}".format(exc.json))
			log_e("ae.response={}".format(exc.response))
			# if ae.response["code"] == "Request_ResourceNotFound":
			# group didn't exist in Azure
			pass

	def _change_license(self, operation, user_id, sku_id):
		log_a("AzureHandler._change_license() operation: {} user_id: {} sku_id: {}".format(operation, user_id, sku_id))
		data = dict(addLicenses=list(), removeLicenses=list())
		if operation == "add":
			data["addLicenses"].append(dict(disabledPlans=[], skuId=sku_id))
		elif operation == "remove":
			data["removeLicenses"].append(sku_id)
		params = urllib.urlencode(azure_params)
		url = self.uris["user_assign_license"].format(user_id=user_id, params=params)
		return self.call_api("POST", url, data)

	def add_license(self, user_id, sku_id):
		self._change_license("add", user_id, sku_id)

	def remove_license(self, user_id, sku_id):
		self._change_license("remove", user_id, sku_id)

	def list_subscriptions(self, object_id=None, ofilter=None):
		return self._list_objects(object_type="subscription", object_id=object_id, ofilter=ofilter)

	def get_office_web_apps_subscriptions(self):
		subscriptions = list()
		for subscription in self.list_subscriptions()["value"]:
			if subscription["appliesTo"] == "User" and subscription["capabilityStatus"] == "Enabled":
				for plan in subscription["servicePlans"]:
					if plan["servicePlanId"] == servicePlanId_SHAREPOINTWAC:
						# found a office web apps plan
						subscriptions.append(subscription)
		return subscriptions

	def list_domains(self, domain_name=None):
		"""
		All domains registered for this tenant, incl. not-verified ones
		:param domain_name: FQDN
		"""
		if domain_name and not domain_name[0] == "'":
			domain_name = "'{}'".format(domain_name)
		return self._list_objects(
			object_type="domain",
			params_extra={"api-version": "beta"},  # TODO: when API version > 1.6, check if "domains" is out of "beta"
			url_extra={"domain_name": domain_name} if domain_name else None)

	def list_tenant_details(self):
		return self._list_objects(object_type="tenantDetail")

	def list_verified_domains(self):
		"""
		Verified domains - only those can be used for userPrincipalName!
		"""
		return self.list_tenant_details()["value"][0]["verifiedDomains"]

	def deactivate_user(self, object_id, rename=False):
		user_obj = self.list_users(objectid=object_id)
		log_p("AzureHandler.deactivate_user() deactivating{} user '{}' / '{}'...".format(
				" and renaming" if rename else "",
				user_obj["displayName"],
				object_id))

		# deactivate user, remove email addresses
		modifications = dict(
			accountEnabled=False,
			otherMails=list()
		)
		if rename:
			name_pattern = "ZZZ_deleted_{time}_{orig}"
			modifications["displayName"] = name_pattern.format(time=time.time(), orig=user_obj["displayName"])
			modifications["mailNickname"] = name_pattern.format(time=time.time(), orig=user_obj["mailNickname"])
			modifications["userPrincipalName"] = name_pattern.format(time=time.time(), orig=user_obj["userPrincipalName"])
		self.modify_user(object_id=object_id, modifications=modifications)

		# remove user from all groups
		groups = self.get_users_direct_groups(object_id)
		group_ids = self.directory_object_urls_to_object_ids(groups["value"])
		for group_id in group_ids:
			self.delete_group_member(group_id=group_id, member_id=object_id)

		# remove all licenses
		for lic in user_obj["assignedLicenses"]:
			self.remove_license(object_id, lic["skuId"])

	def deactivate_group(self, object_id):
		log_a("AzureHandler.deactivate_group() object_id={}".format(object_id))
		group_obj = self.list_groups(objectid=object_id)
		members = self.get_groups_direct_members(object_id)
		member_ids = self.directory_object_urls_to_object_ids(members["value"])
		for member_id in member_ids:
			self.delete_group_member(object_id, member_id)
		name = "ZZZ_deleted_{}_{}".format(time.time(), group_obj["displayName"])
		modifications = dict(
			description="deleted group",
			displayName=name,
			mailEnabled=False,
			mailNickname=name,
		)
		return self.modify_group(object_id=object_id, modifications=modifications)

	def directory_object_urls_to_object_ids(self, urls):
		"""
		:param urls: list of dicts {"url": "https://graph.windows.net/.../directoryObjects/.../..."}
		:return: list of object ids
		"""
		object_ids = list()
		for url in map(itemgetter("url"), urls):
			m = re.match(r"{}/Microsoft.DirectoryServices.*".format(self.uris["directoryObjects"].format(object_id="(.*?)")), url)
			if m:
				object_ids.append(m.groups()[0])
		return object_ids

	@staticmethod
	def _fprints_hide_pw(data, msg):
		"""
		Create string for logging without password.

		:param data: dict to print in {data}, data["passwordProfile"]["password"] will be replaced with "******"
		:param msg: string containing {data}
		:return: msg formatted
		"""
		tmppw = None
		if isinstance(data, dict) and "passwordProfile" in data and "password" in data["passwordProfile"]:
			tmppw = data["passwordProfile"]["password"]
			data["passwordProfile"]["password"] = "******"
		msg = msg.format(data=data)
		if tmppw:
			data["passwordProfile"]["password"] = tmppw
		return msg

	@classmethod
	def _prepare_data(cls, data):
		if not data:
			return data
		assert isinstance(data, dict)

		res = dict()
		for k, v in data.items():
			if isinstance(v, dict):
				res[k] = cls._prepare_data(v)
			try:
				if azure_attribute_types[k] == list and not isinstance(v, list) and isinstance(v, collections.Iterable):
					res[k] = [v]  # list("str") -> ["s", "t", "r"] and list(dict) -> [k, e, y, s]  :/
				else:
					if v is None:
						# don't do unicode(None)
						val = None
					else:
						val = azure_attribute_types[k](v)

					if k in res and isinstance(res[k], list):
						res[k].append(val)
					else:
						res[k] = val
			except KeyError:
				raise UnkownTypeError("Attribute '{}' not in azure_attribute_types mapping.".format(k))
		return res
