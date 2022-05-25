import sys
import os
from collections import UserDict
from time import strptime

import mock
import vcr

from test import DOMAIN_PATH, ALIASDOMAIN

CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))

# Mocking pwd.getpwnam("listener").pw_uid
pwd_module = mock.MagicMock()
m = mock.Mock()
m.pw_uid = 1000
pwd_module.getpwnam.return_value = m
sys.modules['pwd'] = pwd_module

# Mocking grp.getgrnam("nogroup").gr_gid
grp_module = mock.MagicMock()
m = mock.Mock()
m.gr_gid = 1000
grp_module.getgrnam.return_value = m
sys.modules['grp'] = grp_module

debug_module = mock.MagicMock()
sys.modules['univention.debug'] = debug_module

config_registry = mock.MagicMock()
sys.modules['univention.config_registry'] = config_registry
sys.modules['univention.lib.i18n'] = mock.MagicMock()
sys.modules['univention.config_registry.frontend'] = mock.MagicMock()

from univention.office365.api.account import AzureAccount
from univention.office365.api.msgraphwrapper import MSGraphWrapper
from univention.office365.api.token import Token


# This method will be used by the mock to replace requests.get
def mocked_requests_request(*args, **kwargs):
	class MockResponse(UserDict):
		def __init__(self, json_data, status_code):
			super(MockResponse, self).__init__()
			self.json_data = json_data
			self.status_code = status_code
			self.content = json_data

		def json(self):
			return self.json_data

	return MockResponse({"expires_in": 100}, 200)

# @mock.patch('requests.request', side_effect=mocked_requests_request)
@mock.patch('shutil.move')
@vcr.use_cassette('vcr_cassettes/login_info.yml')
def test_graph_api_login(shutil_mock):
	"""Tests an API call to get a TV show's info"""
	ucr = mock.MagicMock()
	ucr.__getitem__.return_value = ''
	account = AzureAccount(ALIASDOMAIN, DOMAIN_PATH)
	account.load_ids_from_file()
	graph_api = MSGraphWrapper(ucr, account)
	response = graph_api._login(force_new_token=True)
	assert isinstance(response, Token)
	assert response['expires_on'] and strptime(response['expires_on'], "%Y-%m-%dT%H:%M:%S")
	assert shutil_mock.called_once()
