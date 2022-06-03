import json
import requests
from typing import Dict, Optional, Any, List, Callable


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
				self.message += (
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


class GenericGraphError(MSGraphError):

	def __init__(self, parent_exception):
		# type: (MSGraphError) -> None
		self.message = parent_exception.message
		self.expected_status = parent_exception.expected_status
		self.response = parent_exception.response


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


def exception_decorator(func):
	# type: (Callable) -> Callable
	def inner(*args, **kwargs):
		# type: (List[Any], Dict[str, Any]) -> Any
		try:
			return func(*args, **kwargs)
		except MSGraphError as e:
			if hasattr(e, "response"):
				response = e.response
				headers = response.headers
				if headers.get("Content-Type", "") == "application/json":
					json_data = response.json()
					error_code = json_data.get("error", {}).get("code", None)
					if error_code:
						exception_class = getattr(__import__(__name__), error_code[0].upper() + error_code[1:], None)
						if exception_class:
							raise exception_class(e)
						else:
							raise
				else:
					raise

	return inner
