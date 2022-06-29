# -*- coding: utf-8 -*-
#
# Univention Office 365 - core_exceptions
#
# Copyright 2016-2022 Univention GmbH
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


import json
import requests
from typing import Dict, Optional, Any, List, Callable

import six

from univention.office365.utils.utils import jsonify


class MSGraphError(Exception):

	def __init__(self, response, message="", expected_status=None):
		# type: (requests.Response, str, List) -> None
		"""
			The Graph API (as well as the Azure API) is consistent in that way,
			that both return a small number of success values as http response
			status code and a larger number of possible error messages, which
			are much more consistent across different endpoints. This function
			is there to take advantage of that fact, and it provides all the
			information required to fix any problem: all request headers and
			the request body alongside with the responses counterparts.

			@return an Exception of type GraphError
		"""
		self.expected_status = expected_status or []
		self.response = response
		self.message = message
		if isinstance(response, str):
			self.message += response

		elif isinstance(response, requests.Response):
			self.message += "HTTP response status: {num}\n".format(
				num=response.status_code
			)
			self.message += "HTTP response expected status: {expected_status}\n".format(expected_status=repr(expected_status))
			if hasattr(response, 'headers'):
				req_header = dict(response.request.headers)
				if "Authorization" in req_header:
					req_header["Authorization"] = "XXX"
				self.message += (
					"> request url: {req_url}\n\n"
					"> request header: {req_headers}\n\n"
					"> request body: {req_body}\n\n"
					"> response header: {headers}\n\n"
					"> response body: {body}\n\n"
				).format(
					req_url=str(response.request.url),
					req_headers=json.dumps(req_header, indent=2),
					req_body=self._try_to_prettify(response.request.body or "-NONE-"),
					headers=json.dumps(dict(response.headers), indent=2),
					body=self._try_to_prettify(response.content or "-NONE-")
				)
		elif response is None:
			self.message += "The response was of type `None`"
		else:
			self.message += 'unexpected error'
		super(MSGraphError, self).__init__(self.message)

	@staticmethod
	def _try_to_prettify(json_string):
		# type: (str) -> str
		try:
			return json.dumps(json.loads(json_string), indent=2)
		except ValueError:
			return json_string


class GenericGraphError(Exception):

	def __init__(self, parent_exception):
		# type: (MSGraphError) -> None
		self.message = parent_exception.message
		self.expected_status = parent_exception.expected_status
		self.response = parent_exception.response
		super(GenericGraphError, self).__init__(self.message)


class AccessDenied(GenericGraphError):
	"""
		The caller doesn't have permission to perform the action.
	"""
	description = "The caller doesn't have permission to perform the action."


class ActivityLimitReached(GenericGraphError):
	"""
		The app or user has been throttled.
	"""
	description = "The app or user has been throttled."


class ExtensionError(GenericGraphError):
	"""
		The mailbox is located on premises and the Exchange server does not support federated Microsoft Graph requests, or an application policy prevents the application from accessing the mailbox.
	"""
	description = "The mailbox is located on premises and the Exchange server does not support federated Microsoft Graph requests, or an application policy prevents the application from accessing the mailbox."


class GeneralException(GenericGraphError):
	"""
		An unspecified error has occurred.
	"""
	description = "An unspecified error has occurred."


class InvalidRange(GenericGraphError):
	"""
		The specified byte range is invalid or unavailable.
	"""
	description = "The specified byte range is invalid or unavailable."


class InvalidRequest(GenericGraphError):
	"""
		The request is malformed or incorrect.
	"""
	description = "The request is malformed or incorrect."

class NotFound(GenericGraphError):
	"""
		The resource could not be found.
	"""
	description = "The resource could not be found."

class ItemNotFound(GenericGraphError):
	"""
		The resource could not be found.
	"""
	description = "The resource could not be found."


class MalwareDetected(GenericGraphError):
	"""
		Malware was detected in the requested resource.
	"""
	description = "Malware was detected in the requested resource."


class NameAlreadyExists(GenericGraphError):
	"""
		The specified item name already exists.
	"""
	description = "The specified item name already exists."


class NotAllowed(GenericGraphError):
	"""
		The action is not allowed by the system.
	"""
	description = "The action is not allowed by the system."


class NotSupported(GenericGraphError):
	"""
		The request is not supported by the system.
	"""
	description = "The request is not supported by the system."


class ResourceModified(GenericGraphError):
	"""
		The resource being updated has changed since the caller last read it, usually an eTag mismatch.
	"""
	description = "The resource being updated has changed since the caller last read it, usually an eTag mismatch."


class ResyncRequired(GenericGraphError):
	"""
		The delta token is no longer valid, and the app must reset the sync state.
	"""
	description = "The delta token is no longer valid, and the app must reset the sync state."


class ServiceNotAvailable(GenericGraphError):
	"""
		The service is not available. Try the request again after a delay. There may be a Retry-After header.
	"""
	description = "The service is not available. Try the request again after a delay. There may be a Retry-After header."


class SyncStateNotFound(GenericGraphError):
	"""
		The sync state generation is not found. The delta token is expired and data must be synchronized again.
	"""
	description = "The sync state generation is not found. The delta token is expired and data must be synchronized again."


class QuotaLimitReached(GenericGraphError):
	"""
		The user has reached their quota limit.
	"""
	description = "The user has reached their quota limit."


class Unauthenticated(GenericGraphError):
	"""
		The caller is not authenticated.
	"""
	description = "The caller is not authenticated."


class AddLicenseError(GenericGraphError):
	def __init__(self, msg, user_id, sku_id, chained_exc=None, *args, **kwargs):
		# type: (str,str,str, Optional[Exception], List[Any], Dict[str, Any]) -> None
		self.user_id = user_id
		self.sku_id = sku_id
		self.message = msg
		# super(AddLicenseError, self).__init__() # TODO revisar


class GraphPermissionError(GenericGraphError):
	description = "Forbidden Error. Your application may not have the correct \npermissions for the Microsoft Graph API.\nPlease check https://help.univention.com/t/18453.\n"


class UnauthorizedError(GenericGraphError):
	description = "Authorization failed\n"


class InternalServerError(GenericGraphError):
	description = "Internal server error\r%s"


def exception_decorator(func):
	# type: (Callable) -> Callable
	status_codes_messages = {
		403: GraphPermissionError,
		401: UnauthorizedError,
		500: InternalServerError
	}

	def inner(*args, **kwargs):
		# type: (List[Any], Dict[str, Any]) -> Any
		try:
			return func(*args, **kwargs)
		except MSGraphError as e:
			status_code = 500 if 500 <= e.response.status_code <= 599 else e.response.status_code
			if status_code in status_codes_messages:
				exception_class = status_codes_messages[status_code]
				e.message = exception_class.description + e.message
				raise exception_class(e)
			elif e.response.headers.get("Content-Type", "") == "application/json" and hasattr(e.response, "json") and e.response.json():
				if six.PY2:
					json_data = jsonify(e.response.json(), "utf-8")
				else:
					json_data = e.response.json()
				error = json_data.get("error", {})
				error_code = error.get("code", None)
				innererror = error.get("innererror", error.get("innerError", {})).get("code", None)
				if innererror:
					exception_class = globals().get(innererror[0].upper() + innererror[1:], None)
					if exception_class:
						raise exception_class(e)
				if error_code:
					exception_class = globals().get(error_code[0].upper() + error_code[1:], None)
					if exception_class:
						raise exception_class(e)
			raise e

	return inner
