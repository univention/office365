#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module to provision accounts in MS Azure
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
import pprint
import requests

from univention.office365.azure_auth import AzureAuth, log_a, log_e, log_ex, log_p, resource_url


azure_params = {"api-version": "1.6"}


def _get_azure_uris(tenant_id):
	graph_base_url = "{0}/{1}".format(resource_url, tenant_id)

	return dict(
		directoryObjects="%s/directoryObjects/{object_id}" % graph_base_url,
		users="%s/users?{params}" % graph_base_url,
		user="%s/users/{object_id}?{params}" % graph_base_url,
		user_assign_license="%s/users/{user_id}/assignLicense?{params}" % graph_base_url,
		getMemberObjects="%s/{resource_collection}/{resource_id}/getMemberObjects?{params}" % graph_base_url,
		getMemberGroups="%s/{resource_collection}/{resource_id}/getMemberGroups?{params}" % graph_base_url,
		getObjectsByObjectIds="%s/getObjectsByObjectIds?{params}" % graph_base_url,
		groups="%s/groups?{params}" % graph_base_url,
		group="%s/groups/{object_id}?{params}" % graph_base_url,
		group_members_direct="%s/groups/{group_id}/$links/members?{params}" % graph_base_url,
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
		super(ApiError, self).__init__(msg)
		self.response = response


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

		tries = 0
		MAX_TRIES = 2
		response = None
		response_json = None
		access_token = self.auth.get_access_token()
		while tries < MAX_TRIES:   # TODO: is this really necessary? Does it always work? Shouldn't this be checked in get_access_token()? Keep it during development, grep in log for 'TRY' to check.
			tries += 1
			log_a("_call_api() **** TRY {} ****".format(tries))
			headers["Authorization"] = "Bearer {}".format(access_token)

			log_p("_call_api() {} {} data: {}".format(method.upper(), url, data))
			# log_a("_call_api() headers: {}".format(headers))
			# log_a("_call_api() my request id: {}".format(request_id))

			requests_func = getattr(requests, method.lower())
			args = dict(url=url, headers=headers, data=data, verify=True)
			if method.upper() in ["PATCH", "POST"]:
				headers["Content-Type"] = "application/json"
				args["data"] = data
			response = requests_func(**args)

			if response is not None:
				try:
					response_json = response.json
					if callable(response_json):
						response_json = response_json()
				except ValueError:
					if method.upper() in ["DELETE", "PATCH", "PUT"]:
						# no response expected
						pass
					else:
						log_ex("response is not JSON. response.__dict__: {}".format(response.__dict__))
				log_p("_call_api() status: {}".format(response.status_code))
				if hasattr(response, "reason"):
					log_p("_call_api() reason: {}".format(response.reason))

				if 200 <= response.status_code <= 299:
					break
				else:
					log_a("_call_api() my request id: {} server request id: {}".format(request_id, response.headers.get("request-id")))
					log_a("_call_api() response(type: {}): {}".format(type(response), pprint.pformat(response.__dict__)))
					if response_json:
						log_a("_call_api() response_json(type: {}): JSON: {}".format(type(response_json), pprint.pformat(response_json)))

					if response_json and "odata.error" in response_json:
						err_code = response_json["odata.error"]["code"]
					else:
						err_code = "Unknown error code, complete response: {}".format(response)
					log_e("Error: {}".format(response.status_code, err_code))
					if response.status_code == 401 and err_code in ["Authentication_ExpiredToken", "Authentication_MissingOrMalformed"]:
						log_p("Retrying with fresh token...")
						access_token = self.auth.retrieve_access_token()
						continue
					else:
						log_e("Calling API: {}".format(response))
						raise ApiError(response)
			else:
				log_e("_call_api() response is None")
		else:
			log_e("Calling API: {}".format(response))
			raise ApiError(response)
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

	def list_groups(self, objectid=None, ofilter=None):
		return self._list_objects(object_type="group", object_id=objectid, ofilter=ofilter)

	def _create_object(self, object_type, attributes):
		assert object_type in ["user", "group"], 'Currently only "user" and "group" supported.'
		assert type(attributes) == dict
		assert "displayName" in attributes
		attrs = dict(attributes)
		if "password" in attrs:
			attrs["password"] = "******"
		log_p("Creating {} with properties: {}.".format(object_type, attrs))

		data = json.dumps(attributes)
		params = urllib.urlencode(azure_params)
		url = self.uris[object_type + "s"].format(params=params)
		return self.call_api("POST", url, data)

	def create_user(self, name):
		attributes = {
			"accountEnabled": True,
			"displayName": name,
			"mailNickname": name,
			"passwordProfile": {
				"password": "univention.99",
				"forceChangePasswordNextLogin": False},
			"userPrincipalName": "{0}@{1}".format(name, "univentiontest.onmicrosoft.com")}  # TODO: retrieve domain from Azure
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
		log_p("Modifying {} with object_id {} and modifications {}...".format(object_type, object_id, modifications))

		params = urllib.urlencode(azure_params)
		url = self.uris[object_type].format(object_id=object_id, params=params)
		data = json.dumps(modifications)
		return self.call_api("PATCH", url, data)

	def modify_user(self, object_id, modifications):
		return self._modify_objects(object_type="user", object_id=object_id, modifications=modifications)

	def modify_group(self, object_id, modifications):
		return self._modify_objects(object_type="group", object_id=object_id, modifications=modifications)

	def _delete_objects(self, object_type, object_id):
		assert object_type in ["user", "group"], 'Currently only "user" and "group" supported.'
		assert type(object_id) == str, "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."
		log_p("Deleting {} with object_id {}...".format(object_type, object_id))

		params = urllib.urlencode(azure_params)
		url = self.uris[object_type].format(object_id=object_id, params=params)
		return self.call_api("DELETE", url)

	def delete_user(self, object_id):
		return self._delete_objects(object_type="user", object_id=object_id)

	def delete_group(self, object_id):
		return self._delete_objects(object_type="group", object_id=object_id)

	def _member_of_(self, obj, object_id):
		log_p("Querying memberOf {} for user with object_id {}...".format(obj, object_id))
		assert type(object_id) == str, "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."

		data = json.dumps({"securityEnabledOnly": True})
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
		log_p("Looking for objects with IDs: {}...".format(object_ids))
		assert type(object_ids) == list, "Parameter object_ids must be a list of object IDs."

		data = json.dumps({"objectIds": object_ids})
		params = urllib.urlencode(azure_params)
		url = self.uris["getObjectsByObjectIds"].format(params=params)
		return self.call_api("POST", url, data)

	def get_groups_direct_members(self, group_id):
		log_p("Fetching direct members of group {}...".format(group_id))
		assert type(group_id) in [str, unicode], "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."

		params = urllib.urlencode(azure_params)
		url = self.uris["group_members_direct"].format(group_id=group_id, params=params)
		return self.call_api("GET", url)

	def add_objects_to_group(self, group_id, object_ids):
		assert type(group_id) == str, "The ObjectId must be a string of form '893801ca-e843-49b7-9f64-7a4590b72769'."
		assert type(object_ids) == list, "object_ids must be a non-empty list of objectID strings."
		assert len(object_ids) > 0, "object_ids must be a non-empty list of objectID strings."
		log_p("Adding objects %r to group {}...".format(object_ids, group_id))

		if len(object_ids) == 1:
			objs = {"url": self.uris["directoryObjects"].format(object_id=object_ids[0])}
		else:
			objs = {"url": [self.uris["directoryObjects"].format(object_id=oid) for oid in object_ids]}
			raise NotImplementedError("Adding multiple objects to a group doesn't work for unknown reason.")  # TODO: ask MS support

		data = json.dumps(objs)
		params = urllib.urlencode(azure_params)
		url = self.uris["group_members_direct"].format(group_id=group_id, params=params)
		return self.call_api("POST", url, data=data)

	def _change_license(self, operation, user_id, license_id):  # TODO: possibly change signature to support disabling plans
		log_a("_change_license() operation: {} user_id: {} license_id: {}".format(operation, user_id, license_id))
		_data = dict(addLicenses=list(), removeLicenses=list())
		if operation == "add":
			_data["addLicenses"].append(dict(disabledPlans=[], skuId=license_id))
		elif operation == "remove":
			_data["removeLicenses"].append(license_id)
		data = json.dumps(_data)
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
