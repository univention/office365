#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle Azure API calls
#
# Copyright 2015 Univention GmbH
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

from univention.office365.azure_auth import AzureAuth, log_a, log_e, log_ex, log_p, resource_url


azure_params = {"api-version": "1.6"}
azure_attribute_types = dict(
	accountEnabled=bool,
	assignedLicenses=list,
	city=unicode,
	country=unicode,
	department=unicode,
	displayName=unicode,
	facsimileTelephoneNumber=unicode,
	givenName=unicode,
	immutableId=unicode,
	jobTitle=unicode,
	mail=unicode,
	mailNickname=unicode,
	mobile=unicode,
	otherMails=list,
	passwordPolicies=unicode,
	passwordProfile=dict,
	password=unicode,
	forceChangePasswordNextLogin=bool,
	physicalDeliveryOfficeName=unicode,
	postalCode=unicode,
	preferredLanguage=unicode,
	state=unicode,
	streetAddress=unicode,
	surname=unicode,
	telephoneNumber=unicode,
	thumbnailPhoto=bytes,
	usageLocation=unicode,
	userPrincipalName=unicode,
	userType=unicode
)

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


class ApiError(Exception):
	def __init__(self, response):
		msg = "Communication error."
		if hasattr(response, "json"):
			j = response.json
			if callable(j):  # requests version compatibility
				j = j()
			msg = j["odata.error"]
		self.response = response
		log_e(msg)
		super(ApiError, self).__init__(msg)


class UnkownTypeError(Exception):
	pass


class AzureHandler(object):
	def __init__(self, listener, name):
		self.listener = listener
		self.name = name
		self.auth = AzureAuth(listener, name)
		self.uris = _get_azure_uris(self.auth.tenant_id)

	def call_api(self, method, url, data=None):
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

		data = AzureHandler._prepare_data(data)
		# hide password
		msg = AzureHandler._fprints_hide_pw(data, "AzureHandler.call_api() %s %s data: {data}" % (method.upper(), url))
		log_p(msg)

		args = dict(url=url, headers=headers, verify=True)
		if method.upper() in ["PATCH", "POST"]:
			headers["Content-Type"] = "application/json"
			args["data"] = json.dumps(data)

		requests_func = getattr(requests, method.lower())
		response = requests_func(**args)

		if response is not None:
			try:
				response_json = response.json
				if callable(response_json):
					response_json = response_json()
			except (TypeError, ValueError):
				if method.upper() in ["DELETE", "PATCH", "PUT"]:
					# no response expected
					pass
				else:
					log_ex("AzureHandler.call_api() response is not JSON. response.__dict__: {}".format(response.__dict__))

			log_p("AzureHandler.call_api() status: {} ({})".format(
					response.status_code,
					"OK" if 200 <= response.status_code <= 299 else "FAIL"))
			if hasattr(response, "reason"):
				log_p("AzureHandler.call_api() reason: {}".format(response.reason))

			if not (200 <= response.status_code <= 299):
				raise ApiError(response)
		else:
			log_e("AzureHandler.call_api() response is None")
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

	def _create_object(self, object_type, attributes):
		assert object_type in ["user", "group"], 'Currently only "user" and "group" supported.'
		assert type(attributes) == dict
		assert "displayName" in attributes

		# hide password
		msg = AzureHandler._fprints_hide_pw(attributes, "AzureHandler._create_object() Creating %s with properties: {data}" % object_type)
		log_p(msg)

		params = urllib.urlencode(azure_params)
		url = self.uris[object_type + "s"].format(params=params)
		return self.call_api("POST", url, attributes)

	def create_user(self, attributes):
		# if user exists, modify it instead
		user = self.list_users(ofilter="userPrincipalName eq '{}'".format(attributes["userPrincipalName"]))
		if user["value"]:
			log_p("AzureHandler.create_user() User '{}' exists, modifying it.".format(user["value"][0]["userPrincipalName"]))
			return self._modify_objects(object_type="user", object_id=user["value"][0]["objectId"], modifications=attributes)
		else:
			return self._create_object(object_type="user", attributes=attributes)

	def create_group(self, name):
		attributes = {
			"displayName": name,
			"mailEnabled": False,
			"mailNickname": name,
			"securityEnabled": True}
		return self._create_object(object_type="group", attributes=attributes)

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
		log_a("AzureHandler._modify_objects() Modifying {} with object_id {} and modifications {}...".format(object_type, object_id, modifications))

		params = urllib.urlencode(azure_params)
		url = self.uris[object_type].format(object_id=object_id, params=params)
		return self.call_api("PATCH", url, modifications)

	def modify_user(self, object_id, modifications):
		return self._modify_objects(object_type="user", object_id=object_id, modifications=modifications)

	def modify_group(self, object_id, modifications):
		return self._modify_objects(object_type="group", object_id=object_id, modifications=modifications)

	def _delete_objects(self, object_type, object_id):
		assert object_type in ["user", "group"], 'Currently only "user" and "group" supported.'
		assert type(object_id) == str, "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."
		log_a("AzureHandler._delete_objects() Deleting {} with object_id {}...".format(object_type, object_id))

		params = urllib.urlencode(azure_params)
		url = self.uris[object_type].format(object_id=object_id, params=params)
		return self.call_api("DELETE", url)

	def delete_user(self, object_id):
		#
		# MS has changed the permissions: "due to recent security enhancement to AAD the application which is
		# accessing the AAD through Graph API should have a role called Company Administrator"...
		#
		# https://github.com/Azure-Samples/active-directory-dotnet-graphapi-console/issues/27
		# https://support.microsoft.com/en-us/kb/3004133
		# http://stackoverflow.com/questions/31834003/azure-ad-change-user-password-from-custom-app
		#
		# So for now use deactivte_user() instead of _delete_objects().
		#

		# return self._delete_objects(object_type="user", object_id=object_id)
		return self.deactivate_user(object_id)

	def delete_group(self, object_id):
		return self._delete_objects(object_type="group", object_id=object_id)

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
		log_a("AzureHandler.resolve_object_ids() Looking for objects with IDs: {}...".format(object_ids))
		assert type(object_ids) == list, "Parameter object_ids must be a list of object IDs."

		data = {"objectIds": object_ids}
		params = urllib.urlencode(azure_params)
		url = self.uris["getObjectsByObjectIds"].format(params=params)
		return self.call_api("POST", url, data)

	def get_groups_direct_members(self, group_id):
		log_a("AzureHandler.get_groups_direct_members() Fetching direct members of group {}...".format(group_id))
		assert type(group_id) in [str, unicode], "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."

		params = urllib.urlencode(azure_params)
		url = self.uris["group_members"].format(group_id=group_id, params=params)
		return self.call_api("GET", url)

	def add_objects_to_group(self, group_id, object_ids):
		assert type(group_id) == str, "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."
		assert type(object_ids) == list, "object_ids must be a non-empty list of objectID strings."
		assert len(object_ids) > 0, "object_ids must be a non-empty list of objectID strings."
		log_a("AzureHandler.add_objects_to_group() Adding objects %r to group {}...".format(object_ids, group_id))

		if len(object_ids) == 1:
			objs = {"url": self.uris["directoryObjects"].format(object_id=object_ids[0])}
		else:
			objs = {"url": [self.uris["directoryObjects"].format(object_id=oid) for oid in object_ids]}
			raise NotImplementedError("Adding multiple objects to a group doesn't work for unknown reason.")  # TODO: ask MS support

		params = urllib.urlencode(azure_params)
		url = self.uris["group_members"].format(group_id=group_id, params=params)
		return self.call_api("POST", url, data=objs)

	def _change_license(self, operation, user_id, license_id):  # TODO: possibly change signature to support disabling plans
		log_a("AzureHandler._change_license() operation: {} user_id: {} license_id: {}".format(operation, user_id, license_id))
		data = dict(addLicenses=list(), removeLicenses=list())
		if operation == "add":
			data["addLicenses"].append(dict(disabledPlans=[], skuId=license_id))
		elif operation == "remove":
			data["removeLicenses"].append(license_id)
		params = urllib.urlencode(azure_params)
		url = self.uris["user_assign_license"].format(user_id=user_id, params=params)
		return self.call_api("POST", url, data)

	def add_license(self, user_id, license_id):
		self._change_license("add", user_id, license_id)

	def remove_license(self, user_id, license_id):
		self._change_license("remove", user_id, license_id)

	def list_subscriptions(self, objectid=None, ofilter=None):
		return self._list_objects(object_type="subscription", object_id=objectid, ofilter=ofilter)

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

	def deactivate_user(self, user_id):
		user_obj = self.list_users(objectid=user_id)

		# deactivate user, remove email addresses
		self._modify_objects(object_type="user", object_id=user_id, modifications={
			"accountEnabled": False,
			"otherMails": [],
			"immutableId": "deactivated_{}".format(user_obj["immutableId"])
		})

		# remove user from all groups
		groups = self.get_users_direct_groups(user_id)
		params = urllib.urlencode(azure_params)
		for gr in groups["value"]:
			group_obj = self.call_api("GET", "{}?{}".format(gr["url"], params))
			url = self.uris["group_member"].format(group_id=group_obj["objectId"], member_id=user_id, params=params)
			self.call_api("DELETE", url)

		# remove all licenses
		for lic in user_obj["assignedLicenses"]:
			self.remove_license(user_id, lic["skuId"])

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

	@staticmethod
	def _prepare_data(data):
		if not data:
			return data
		assert isinstance(data, dict)

		res = dict()
		for k, v in data.items():
			if isinstance(v, dict):
				res[k] = AzureHandler._prepare_data(v)
			try:
				if azure_attribute_types[k] == list and not isinstance(v, list) and isinstance(v, collections.Iterable):
					res[k] = [v]  # list("str") -> ["s", "t", "r"] and list(dict) -> [k, e, y, s]  :/
				else:
					if k in res and isinstance(res[k], list):
						res[k].append(azure_attribute_types[k](v))
					else:
						res[k] = azure_attribute_types[k](v)
			except KeyError:
				raise UnkownTypeError("Attribute '{}' not in azure_attribute_types mapping.".format(k))
		return res
