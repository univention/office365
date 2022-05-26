import contextlib
import os
import re
import sys
from unittest import mock

import pytest

from test.utils import all_methods_called

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

sys.modules['univention.debug'] = mock.MagicMock()
sys.modules['univention.config_registry'] = mock.MagicMock()
sys.modules['univention.lib.i18n'] = mock.MagicMock()
sys.modules['univention.config_registry.frontend'] = mock.MagicMock()
sys.modules["os"].chown = mock.MagicMock()

from univention.office365.microsoft import account as accound_M
from test import ALIASDOMAIN, DOMAIN_PATH, DOMAIN_2

CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))


@contextlib.contextmanager
def mock_JsonStorage():
	# type: () -> mock.MagicMock
	old_j = accound_M.JsonStorage
	accound_M.JsonStorage = mock.MagicMock()
	yield accound_M.JsonStorage
	accound_M.JsonStorage = old_j


@contextlib.contextmanager
def mock_json():
	# type: () -> mock.MagicMock
	old_j = accound_M.json
	accound_M.json = mock.MagicMock()
	yield accound_M.json
	accound_M.json = old_j

class TestAzureAccount:

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, accound_M.AzureAccount, ["update", "check_token", "update_and_save_token",  "values", "items", "clear", "pop", "copy", "get", "fromkeys", "setdefault", "keys", "popitem", "parse_id_token", "write_saml_setup_script", "create_local"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	def test_load_ids_from_file(self):
		# type: () -> None
		""" Test Azure account """

		account = accound_M.AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
		account.load_ids_from_file()
		assert account["domain"] == DOMAIN_2
		assert account["application_id"]
		assert account["client_id"]
		assert account["client_id"] == account["application_id"]
		assert account["directory_id"]
		assert account["adconnection_id"]
		assert account["directory_id"] == account["adconnection_id"]

	def test_client_assertion(self):
		# type: () -> None
		""" Test Azure account """
		account = accound_M.AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
		account.load_ids_from_file()
		assert account.client_assertion()
		assert isinstance(account.client_assertion(), str)


	def test_get_authorization_url(self):
		# type: () -> None
		""""""
		account = accound_M.AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
		url = account.get_authorization_url()
		assert url.startswith("https://login.microsoftonline.com/{}/oauth2/authorize?".format(account.get("adconnection_id")))

	def test_get_domain(self):
		# type: () -> None
		""""""
		account = accound_M.AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
		assert account.get_domain() == account["domain"]

	# @pytest.mark.skip
	# def test_parse_id_token(self):
	#	# type: () -> None
	# 	""""""
	# 	account = accound_M.AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
	# 	account.parse_id_token()
	# 	raise NotImplementedError

	def test_uninitialize(self):
		# type: () -> None
		""""""
		with mock_JsonStorage():
			account = accound_M.AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
			account.uninitialize()
			accound_M.JsonStorage.return_value.purge.assert_called()

	def test_store_ids(self):
		# type: () -> None
		""""""
		with mock_JsonStorage() as JsonStorage_mocked:
			account = accound_M.AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
			data = {"test": "test"}
			account.store_ids(**data)
			JsonStorage_mocked.return_value.write.assert_called_with(**data)

	def test_is_initialized(self):
		# type: () -> None
		""""""
		account = accound_M.AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
		assert account.is_initialized()

	def test_store_manifest(self):
		# type: () -> None
		""""""
		with mock_json() as json_mocked:
			account = accound_M.AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
			manifest = mock.MagicMock()
			account.store_manifest(manifest)
			json_mocked.dump.assert_called()


