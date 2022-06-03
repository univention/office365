# -*- coding: utf-8 -*-
from typing import Optional


class GenericLoginException(Exception):
	def __init__(self, msg, chained_exc=None, adconnection_alias=None, *args, **kwargs):
		# type: (str, Optional[Exception], Optional[str], List, Dict) -> None
		self.chained_exc = chained_exc
		self.adconnection_alias = adconnection_alias
		super(GenericLoginException, self).__init__(msg, *args, **kwargs)  # TODO revisar


class TokenError(GenericLoginException):
	def __init__(self, msg, response=None, *args, **kwargs):
		# type: (str, Optional[requests.Response], List, Dict) -> None
		self.response = response
		if response and hasattr(response, "json"):
			j = response.json
			if callable(response.json):  # requests version compatibility
				j = j()
			self.error_description = j["error_description"]
		super(TokenError, self).__init__(msg, *args, **kwargs)


class IDTokenError(GenericLoginException):
	pass


class TokenValidationError(GenericLoginException):
	pass


class NoIDsStored(GenericLoginException):
	pass


class ManifestError(GenericLoginException):
	pass


class WriteScriptError(GenericLoginException):
	pass


class ADConnectionIDError(GenericLoginException):
	pass
