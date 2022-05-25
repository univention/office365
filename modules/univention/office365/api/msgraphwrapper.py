import json
import time

import requests

from univention.office365.api.account import AzureAccount
from univention.office365.api.core import MSGraphApiCore
from univention.office365.api.exceptions import GraphError
from univention.office365.api.urls import URLs
from univention.office365.api_helper import get_http_proxies
from univention.office365.logging2udebug import get_logger

logger = get_logger("office365", "o365")


class MSGraphWrapper:
	def __init__(self, ucr, account: AzureAccount):
		self.account = account
		# proxies must be set before any attempt to call the API
		self.proxies = get_http_proxies(ucr, logger)
		self.login_retry_count = 3
		self.api_core = None

	def _login(self, force_new_token=False):
		# If not forced to get a new token, check if the token is still valid
		if not force_new_token and self.account.token:
			return self.account.token

		# Get new token
		self.api_core = MSGraphApiCore(self.account, response_handlers={504: self._handler_for_504, 400: self._handler_for_504})

		return self.account.token

	def _handler_for_504(self, response):
		if self.login_retry_count > 0:
			self.login_retry_count -= 1
			return self._login(force_new_token=True)
		else:
			raise GraphError(response, "504 Gateway Timeout")
