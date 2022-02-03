#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle Azure API calls
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

from __future__ import absolute_import

import json
import urllib
import uuid
import requests
import collections
import time
import re
from operator import itemgetter
import random
import string
import sys
from six import string_types

from univention.office365.azure_auth import AzureAuth, AzureError, resource_url
from univention.office365.logging2udebug import get_logger

try:
	from json.decoder import JSONDecodeError  # noqa: F811 # python-requests with py3
except ImportError:
	JSONDecodeError = ValueError  # requests with py2

if sys.version_info < (3,):
	unicode = unicode
else:
	unicode = str

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
	securityEnabledOnly=bool,
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
# service plan names
# SWAY                   Sway
# INTUNE_O365            Mobile Device Management for Office 365
# YAMMER_ENTERPRISE      Yammer
# RMS_S_ENTERPRISE       Azure Rights Management (RMS)
# OFFICESUBSCRIPTION     Office Professional Plus
# MCOSTANDARD            Skype for Business Online
# SHAREPOINTWAC          Office Online
# SHAREPOINTENTERPRISE   SharePoint Online
# EXCHANGE_S_ENTERPRISE  Exchange Online Plan 2
_default_azure_service_plan_names = "SHAREPOINTWAC, SHAREPOINTWAC_DEVELOPER, OFFICESUBSCRIPTION, OFFICEMOBILE_SUBSCRIPTION, SHAREPOINTWAC_EDU"

logger = get_logger("office365", "o365")


def _get_azure_uris(adconnection_id):
	graph_base_url = "{0}/{1}".format(resource_url, adconnection_id)

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
		adconnectionDetails="%s/adconnectionDetails?{params}" % graph_base_url,
		invalidateTokens="%s/users/{user_id}/invalidateAllRefreshTokens?{params}" % graph_base_url,
		baseUrl=graph_base_url,
	)


def get_service_plan_names(ucr):
	ucr_service_plan_names = ucr.get("office365/subscriptions/service_plan_names") or _default_azure_service_plan_names
	return [spn.strip() for spn in ucr_service_plan_names.split(",")]


class ApiError(AzureError):
	def __init__(self, response, *args, **kwargs):
		msg = "Communication error."
		if isinstance(response, requests.Response):
			msg += "HTTP response status: {num}\n".format(
			    num=response.status_code
			)
		if hasattr(response, "json"):
			j = response.json
			if callable(j):  # requests version compatibility
				j = j()
			msg = j["odata.error"]["message"]["value"]
			self.json = j
			logger.debug((
				"> request url: {req_url}\n\n"
				"> request header: {req_headers}\n\n"
				"> request body: {req_body}\n\n"
				"> response header: {headers}\n\n"
				"> response body: {body}\n\n"
			).format(
				req_url=str(response.request.url),
				req_headers=json.dumps(dict(response.request.headers), indent=2),
				req_body=self._try_to_prettify(response.request.body or "-NONE-"),
				headers=json.dumps(dict(response.headers), indent=2),
				body=self._try_to_prettify(response.content or "-NONE-")
			))
		self.response = response
		logger.error(msg)
		super(ApiError, self).__init__(msg, *args, **kwargs)

	def _try_to_prettify(self, json_string):
		try:
			return json.dumps(json.loads(json_string), indent=2)
		except ValueError:
			return json_string


class ResourceNotFoundError(ApiError):
	pass


class AddLicenseError(AzureError):
	def __init__(self, msg, user_id, sku_id, chained_exc=None, *args, **kwargs):
		self.user_id = user_id
		self.sku_id = sku_id
		super(AddLicenseError, self).__init__(msg, chained_exc, *args, **kwargs)


class UnkownTypeError(AzureError):
	pass


class AzureHandler(object):
	def __init__(self, ucr, name, adconnection_alias=None):
		self.ucr = ucr
		self.name = name
		self.adconnection_alias = adconnection_alias
		logger.debug('adconnection_alias=%r', adconnection_alias)
		self.auth = AzureAuth(name, adconnection_alias)
		self.uris = _get_azure_uris(self.auth.adconnection_id)
		self.service_plan_names = get_service_plan_names(self.ucr)
		logger.info("service_plan_names=%r", self.service_plan_names)

	def getAzureLogger(self):
		return logger

	def call_api(self, method, url, data=None, retry=0):
		'''
		SUMMARY
		-------

		This function:

		* creates the correct http header for requests against azure
		* support for proxy servers
		* implements pagination
		* implements retry after 10 seconds if error code is 5xx
		* implements basic sanity checks and catches error codes

		ATTRIBUTES
		----------

		method : str
			GET|POST|PATCH|PUT|DELETE|...

		url : str
			string in the form
			protocol://tld.example.com/path/[file]?params

		data : dict
			a json-object (or dict) to be used as payload (json.dumps is
			used for serialization)

		RAISES
		------

		ResourceNotFoundError
			the request returned 404 or an object was not found

		APIError
			every other error

		RETURNS
		-------

		Either a json object, a requests.models.Response object or an
		Exception of type APIError
		'''

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

		values = []
		while url:
			# hide password
			msg = self._fprints_hide_pw(data, "%s %s data: {data}" % (method.upper(), url))
			logger.debug(msg)

			args = dict(url=url, headers=headers, verify=True, proxies=self.auth.proxies, timeout=10)
			if method.upper() in ["PATCH", "POST"] and data:
				headers["Content-Type"] = "application/json"
				args["data"] = json.dumps(data)


			requests_func = getattr(requests, method.lower())
			try:
				response = requests_func(**args)
			except requests.exceptions.Timeout:
				response = requests_func(**args)

			if response is not None:
				try:
					response_json = response.json
					if callable(response_json):  # requests version compatibility
						response_json = response_json()
				except (TypeError, JSONDecodeError) as exc:
					if method.upper() in ["DELETE", "PATCH", "PUT"]:
						# no/empty response expected
						response_json = {}
					elif method.upper() == "POST" and "members" in url:
						# no/empty response expected (add_objects_to_azure_group())
						response_json = {}
					else:
						logger.exception("response is not JSON (adconnection_alias=%r). response.__dict__: %r", self.adconnection_alias, response.__dict__)
						raise ApiError(response, chained_exc=exc, adconnection_alias=self.adconnection_alias)
				logger.info(
					"status: %r (%s)%s (%s %s)",
					response.status_code,
					"OK" if 200 <= response.status_code <= 299 else "FAIL",
					" Code: {}".format(response_json["odata.error"]["code"]) if response_json and "odata.error" in response_json else "",
					method.upper(),
					url)

				if not (200 <= response.status_code <= 299):
					if response.status_code == 404 and response_json["odata.error"]["code"] == "Request_ResourceNotFound":
						raise ResourceNotFoundError(response, adconnection_alias=self.adconnection_alias)
					elif 500 <= response.status_code <= 599:
						# server error
						if retry > 0:
							raise ApiError(response, adconnection_alias=self.adconnection_alias)
						else:
							logger.error("AzureHandler.call_api() Server error. Azure said: %r. Will sleep 10s and then retry one time.", response_json["odata.error"]["message"]["value"])
							time.sleep(10)
							self.call_api(method, url, data=data, retry=retry + 1)
					else:
						raise ApiError(response, adconnection_alias=self.adconnection_alias)
				url = response_json.get("odata.nextLink")
				if url:
					# We are in paging mode, accumulate the batches
					values.extend(response_json["value"])
					if url.startswith('https://') or url.startswith('http://'):
						url += "&api-version=1.6"
					else:
						url = self.uris['baseUrl'] + '/' + url + "&api-version=1.6"
					# TODO do we want paging?
				elif values:
					# If we are in paging mode, get the last batch
					values.extend(response_json["value"])
			else:
				logger.error("AzureHandler.call_api() response is None")
				raise ApiError("Response is None", adconnection_alias=self.adconnection_alias)
		if values:
			# If paging was used, then replace values with accumulated list
			response_json["value"] = values
		return response_json or response

	def _list_objects(self, object_type, object_id=None, ofilter=None, params_extra=None, url_extra=None):
		assert object_type in ["user", "group", "subscription", "domain", "adconnectionDetail"], 'Unsupported object type.'
		if params_extra:
			assert isinstance(params_extra, dict)

		params = dict(**azure_params)
		if params_extra:
			params.update(params_extra)
		if ofilter:
			params["$filter"] = ofilter
		params = urllib.urlencode(params)
		if object_id:
			assert type(object_id) in [str, unicode], 'The ObjectId must be a string.'
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
		msg = self._fprints_hide_pw(attributes, "Creating %s for Azure AD connection %s with properties: {data}" % (object_type, self.adconnection_alias))
		logger.info(msg)

		obj = self._list_objects(object_type=object_type, ofilter="{key} eq '{value}'".format(**obj_id))
		if obj["value"]:
			logger.info("%s %r exists (%s), modifying it.", object_type, obj["value"][0]["displayName"], self.adconnection_alias)

			return self._modify_objects(
				object_type=object_type,
				object_id=obj["value"][0]["objectId"],
				modifications=attributes
			)
		else:
			params = urllib.urlencode(azure_params)
			url = self.uris[object_type + "s"].format(params=params)
			return self.call_api("POST", url, attributes)

	def invalidate_all_tokens_for_user(self, user_id):
		# https://docs.microsoft.com/de-de/previous-versions/azure/ad/graph/api/users-operations#invalidate-all-refresh-tokens-for-a-user
		params = urllib.urlencode(azure_params)
		url = self.uris["invalidateTokens"].format(user_id=user_id, params=params)
		return self.call_api("POST", url)

	def reset_user_password(self, user_id):
		# reset the user password to a random string, to reset the attribute when
		# the last userpassword change happened, pwdLastSet. Bug #49699
		# "Either delegated scope User.ReadWrite.All or Directory.AccessAsUser.All is required to reset a user's password."
		pwdProfile = dict(
			passwordProfile=dict(
				password=self.create_random_pw(),
				forceChangePasswordNextLogin=False
			)
		)
		params = urllib.urlencode(azure_params)
		url = self.uris["user"].format(object_id=user_id, params=params)
		return self.call_api("PATCH", url, pwdProfile)

	def create_user(self, attributes):
		"""
		if user exists, it will be modified instead
		"""
		return self._create_object(
			object_type="user",
			attributes=attributes,
			obj_id={"key": "immutableId", "value": attributes["immutableId"]}
		)

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
			obj_id={"key": "displayName", "value": name}
		)

	def _modify_objects(self, object_type, object_id, modifications):
		assert object_type in ["user", "group"], 'Currently only "user" and "group" supported.'
		assert type(object_id) in [str, unicode], 'The ObjectId must be a string.'
		assert type(modifications) == dict, "Please supply a dict of attr->value to change."

		can_only_be_created_not_modified = ["mobile", "passwordProfile"]
		for attrib in can_only_be_created_not_modified:
			if attrib in modifications:
				# read text at beginning delete_user()
				del modifications[attrib]
				logger.warn("Modifying %r is currently not supported, removed it from modification list.", attrib)
		logger.info("Modifying %s with object_id %r (%s) and modifications %r...", object_type, object_id, self.adconnection_alias, modifications)

		params = urllib.urlencode(azure_params)
		url = self.uris[object_type].format(object_id=object_id, params=params)
		return self.call_api("PATCH", url, modifications)

	def modify_user(self, object_id, modifications):
		return self._modify_objects(object_type="user", object_id=object_id, modifications=modifications)

	def modify_group(self, object_id, modifications):
		if "uniqueMember" in modifications:
			raise RuntimeError("Attribute uniqueMember must be dealt with in listener (adconnection_alias=%r).", self.adconnection_alias)
		return self._modify_objects(object_type="group", object_id=object_id, modifications=modifications)

	def _delete_objects(self, object_type, object_id):
		assert object_type in ["user", "group"], 'Currently only "user" and "group" supported.'
		assert type(object_id) in [str, unicode], "The ObjectId must be a string."
		logger.info("Deleting %s with object_id %r (%s)...", object_type, object_id, self.adconnection_alias)

		params = urllib.urlencode(azure_params)
		url = self.uris[object_type].format(object_id=object_id, params=params)
		try:
			return self.call_api("DELETE", url)
		except ResourceNotFoundError as exc:
			logger.error("Object %r didn't exist: %r (%s)", object_id, exc, self.adconnection_alias)
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

	def _member_of_(self, obj, object_id, resource_collection):
		"""
		Transitive versions (incl nested groups)
		"""
		logger.debug("Querying memberOf %r for %r with object_id %r (%s)...", obj, resource_collection, object_id, self.adconnection_alias)
		assert type(resource_collection) in [str, unicode], "resource_collection must be a string."
		assert type(object_id) in [str, unicode], "The ObjectId must be a string."

		params = urllib.urlencode(azure_params)
		if obj == "groups":
			url = self.uris["getMemberGroups"].format(resource_collection=resource_collection, resource_id=object_id, params=params)
			data = {"securityEnabledOnly": False}
		else:
			url = self.uris["getMemberObjects"].format(resource_collection=resource_collection, resource_id=object_id, params=params)
			data = {"securityEnabledOnly": True}
		return self.call_api("POST", url, data)

	def member_of_groups(self, object_id, resource_collection="users"):
		return self._member_of_("groups", object_id, resource_collection)

	def member_of_objects(self, object_id, resource_collection="users"):
		return self._member_of_("objects", object_id, resource_collection)

	def resolve_object_ids(self, object_ids, object_types=None):
		assert type(object_ids) == list, "Parameter object_ids must be a list of object IDs."

		data = {"objectIds": object_ids}
		params = urllib.urlencode(azure_params)
		url = self.uris["getObjectsByObjectIds"].format(params=params)
		return self.call_api("POST", url, data)

	def get_groups_direct_members(self, group_id):
		assert type(group_id) in [str, unicode], "The ObjectId must be a string."

		params = urllib.urlencode(azure_params)
		url = self.uris["group_members"].format(group_id=group_id, params=params)
		return self.call_api("GET", url)

	def add_objects_to_azure_group(self, group_id, object_ids):
		"""
		Add users and groups to a group in Azure AD
		:param group_id: object_id of azure group
		:param object_ids: list: object_ids of groups
		:return: None
		"""
		assert type(group_id) in [str, unicode], "The ObjectId must be a string."
		assert type(object_ids) == list, "object_ids must be a list."
		assert all(type(o_id) in [str, unicode] for o_id in object_ids), "object_ids must be a list of objectID strings."
		logger.info("Adding objects %r to group %r (%s)...", object_ids, group_id, self.adconnection_alias)

		# remove object's that already member of group
		# if it's just one new member, it's not worth the effort
		if len(object_ids) > 1:
			members = self.get_groups_direct_members(group_id)
			object_ids_already_in_azure = self.directory_object_urls_to_object_ids(members["value"])
			object_ids = set(object_ids) - set(object_ids_already_in_azure)

		# While the Graph API clearly states that multiple objects can be added
		# at once to a group that is no entirely true, as the usual API syntax
		# does not allow it. In the end a MS employee found out, that a OAuth
		# Batch request has to be created and then still only 5 objects can be
		# added at once (https://social.msdn.microsoft.com/Forums/azure/en-US/04113864-51af-4d46-8b13-725e4120433b/graphi-api-how-to-add-many-members-to-a-group).
		# The added complexity is entirely out of proportion for the benefit,
		# so here comes a loop instead.
		for object_id in object_ids:
			if not object_id:
				logger.warn("AzureHandler.add_objects_to_azure_group(): not adding empty object_id to group %r.", group_id)
				continue
			dir_obj_url = self.uris["directoryObjects"].format(object_id=object_id)
			objs = {"url": dir_obj_url}
			params = urllib.urlencode(azure_params)
			url = self.uris["group_members"].format(group_id=group_id, params=params)
			try:
				self.call_api("POST", url, data=objs)
			except ApiError as exc:
				# ignore error if object is already member of group
				if str(exc) == "One or more added object references already exist for the following modified properties: 'members'.":
					logger.info("Ignore ApiError 'One or more added object references already exist ...' in add_objects_to_azure_group, object is already member of group")
				else:
					raise

	def delete_group_member(self, group_id, member_id):
		logger.info("Removing member %r from group %r (%s)...", member_id, group_id, self.adconnection_alias)
		params = urllib.urlencode(azure_params)
		url = self.uris["group_member"].format(group_id=group_id, member_id=member_id, params=params)

		try:
			return self.call_api("DELETE", url)
		except ApiError as exc:
			msg = "ApiError deleting a group member, exc.response={}".format(exc.response)
			if hasattr(exc, "json"):
				msg += " exc.json={}".format(exc.json)
			msg += " exc.__dict__={}".format(exc.__dict__)
			logger.exception(msg)
			# if ae.response["code"] == "Request_ResourceNotFound":
			# group didn't exist in Azure
			pass

	def _change_license(self, operation, user_id, sku_id, deactivate_plans):
		logger.debug(
			"operation: %r user_id: %r sku_id: %r deactivate_plans=%r (%s)",
			operation,
			user_id,
			sku_id,
			deactivate_plans,
			self.adconnection_alias)
		data = dict(addLicenses=list(), removeLicenses=list())
		if operation == "add":
			data["addLicenses"].append(dict(disabledPlans=deactivate_plans if deactivate_plans else [], skuId=sku_id))
		elif operation == "remove":
			data["removeLicenses"].append(sku_id)
		params = urllib.urlencode(azure_params)
		url = self.uris["user_assign_license"].format(user_id=user_id, params=params)
		return self.call_api("POST", url, data)

	def add_license(self, user_id, sku_id, deactivate_plans=None):
		try:
			self._change_license("add", user_id, sku_id, deactivate_plans)
		except ApiError as exc:
			raise AddLicenseError(str(exc), user_id, sku_id, exc)

	def remove_license(self, user_id, sku_id):
		self._change_license("remove", user_id, sku_id, None)

	def list_subscriptions(self, object_id=None, ofilter=None):
		return self._list_objects(object_type="subscription", object_id=object_id, ofilter=ofilter)

	def get_enabled_subscriptions(self):
		subscriptions = list()
		for subscription in self.list_subscriptions()["value"]:
			if subscription["appliesTo"] == "User" and subscription["capabilityStatus"] == "Enabled":
				for plan in subscription["servicePlans"]:
					if plan["servicePlanName"] in self.service_plan_names:
						# found an office plan
						subscriptions.append(subscription)
						break
		return subscriptions

	def list_domains(self, domain_name=None):
		"""
		All domains registered for this adconnection, incl. not-verified ones
		:param domain_name: FQDN
		"""
		if domain_name and not domain_name[0] == "'":
			domain_name = "'{}'".format(domain_name)
		return self._list_objects(
			object_type="domain",
			params_extra={"api-version": "beta"},  # TODO: when API version > 1.6, check if "domains" is out of "beta"
			url_extra={"domain_name": domain_name} if domain_name else None)

	def list_adconnection_details(self):
		return self._list_objects(object_type="adconnectionDetail")

	def list_verified_domains(self):
		"""
		Verified domains - only those can be used for userPrincipalName!
		Use get_verified_domain_from_disk() for user creation.
		"""
		return self.list_adconnection_details()["value"][0]["verifiedDomains"]

	def get_verified_domain_from_disk(self):
		"""
		Get domain name that was configured in wizard.
		:return: str: domain name
		"""
		return self.auth.domain

	def deactivate_user(self, object_id, rename=False):
		user_obj = self.list_users(objectid=object_id)
		logger.info("Deactivating%s user %r / %r (%s)...", " and renaming" if rename else "", user_obj["displayName"], object_id, self.adconnection_alias)

		# deactivate user, remove email addresses
		modifications = dict(
			accountEnabled=False,
			otherMails=list()
		)
		if rename:
			if re.match(r'^ZZZ_deleted_.+_.+', user_obj["userPrincipalName"]):
				# this shouldn't happen
				logger.warn("User %r (%s) already deactivated, ignoring.", user_obj["userPrincipalName"], self.adconnection_alias)
			else:
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
		logger.debug("object_id=%r adconnection_alias=%r", object_id, self.adconnection_alias)
		group_obj = self.list_groups(objectid=object_id)

		if (group_obj["description"] == "deleted group" and group_obj["displayName"].startswith("ZZZ_deleted_") and group_obj["mailNickname"].startswith("ZZZ_deleted_")):
			# group was already deactivated
			logger.warn("Group already deactivated: %r (%s).", group_obj["displayName"], self.adconnection_alias)
			return

		members = self.get_groups_direct_members(object_id)
		member_ids = self.directory_object_urls_to_object_ids(members["value"])
		for member_id in member_ids:
			self.delete_group_member(object_id, member_id)
		name = "ZZZ_deleted_{}_{}".format(time.time(), group_obj["displayName"])
		modifications = dict(
			description="deleted group",
			displayName=name,
			mailEnabled=False,
			mailNickname=name.replace(" ", "_-_"),
		)
		logger.info("Renaming group %r to %r (%s).", group_obj["displayName"], name, self.adconnection_alias)
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
	def create_random_pw():
		# have at least one char from each category in password
		# https://msdn.microsoft.com/en-us/library/azure/jj943764.aspx
		pw = list(random.choice(string.lowercase))
		pw.append(random.choice(string.uppercase))
		pw.append(random.choice(string.digits))
		pw.append(random.choice(u"@#$%^&*-_+=[]{}|\\:,.?/`~();"))
		pw.extend(random.choice(string.ascii_letters + string.digits + u"@#$%^&*-_+=[]{}|\\:,.?/`~();") for _ in range(12))
		random.shuffle(pw)
		return u"".join(pw)

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
				if res[k] and isinstance(res[k], list) and all(isinstance(x, string_types) for x in res[k]):
					# remove duplicates insensitive (can really only happen in 'otherMails')
					list_copy = list()
					for o in res[k]:
						if o.lower() not in [x.lower() for x in list_copy]:
							list_copy.append(o)
					res[k] = list_copy

			except KeyError as exc:
				raise UnkownTypeError("Attribute '{}' not in azure_attribute_types mapping.".format(k), chained_exc=exc)
		return res

# vim: filetype=python noexpandtab tabstop=4 shiftwidth=4 softtabstop=4
