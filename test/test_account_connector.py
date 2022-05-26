import sys

import pytest
from mock import mock
from mock.mock import call
from typing import Type, Set

import univention


def all_methods_called(test_class, class_to_check, exclude):
	# type: (Type, Type, Set[str]) -> Set[str]
	method_list = [func for func in dir(class_to_check) if
				   callable(getattr(class_to_check, func)) and not func.startswith("_")]
	method_list2 = [func[5:] for func in dir(test_class) if
					callable(getattr(test_class, func)) and not func.startswith("_") and func.startswith("test_")]
	diff = set(method_list) - set(method_list2) - set(exclude)
	return diff


pwd_module = mock.MagicMock()
m = mock.Mock()
m.pw_uid = 1000
pwd_module.getpwnam.return_value = m
sys.modules['pwd'] = pwd_module
sys.modules['pwd'] = pwd_module
sys.modules['univention.admin'] = mock.MagicMock()
sys.modules['univention.lib'] = mock.MagicMock()
sys.modules['univention.lib.i18n'] = mock.MagicMock()
sys.modules['univention.admin'].uldap.getAdminConnection.return_value = mock.MagicMock(), mock.MagicMock()
sys.modules['univention.debug'] = mock.MagicMock()
sys.modules['univention.config_registry'] = mock.MagicMock()
sys.modules['univention.config_registry.frontend'] = mock.MagicMock()
sys.modules['univention.ldap_cache.cache'] = mock.MagicMock()
sys.modules['univention.ldap_cache.frontend'] = mock.MagicMock()
sys.modules['univention.lib.i18n'] = mock.MagicMock()
sys.modules['ldap'] = mock.MagicMock()
sys.modules['ldap.filter'] = mock.MagicMock()
sys.modules['os'].chown = mock.MagicMock()

from univention.office365.connector.account_connector import ConnectionsPool




class TestAccountsPool:
	total_accounts = 10
	def setup_method(self):
		# type: () -> None
		with mock.patch("univention.office365.ucr_helper.UCRHelper", name="UCRHelperMocked") as UCRHelper:
			UCRHelper.get_adconnection_aliases = mock.MagicMock(return_value={"alias" + str(x): "id" + str(x) for x in range(0, self.total_accounts)})
			univention.office365.api.account_connector.UCRHelper = UCRHelper

	# def test_completity(self):
	#	# type: () -> None
	# 	diff = all_methods_called(self.__class__, AccountsPool, ["get_not_none_values_as_dict", "set_core", "wait_for_operation", "get_fields", "create_or_modify"])
	# 	assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	@pytest.mark.skip("Not integrated yet")
	def test_status(self):
		# type: () -> None
		self.pool.status()
		assert False

	@pytest.mark.skip("Not integrated yet")
	@mock.patch("univention.office365.api.account_connector.AzureAccount", name="AzureAccountMocked")
	def test_from_ucr(self, azure_account):
		# type: (mock.MagicMock) -> None
		azure_account.side_effect = [mock.MagicMock(name="AzureAccount"+str(x)) for x in range(0, self.total_accounts)]
		ConnectionsPool.from_ucr()

	@pytest.mark.skip("Not integrated yet")
	@mock.patch("univention.office365.api.account_connector.AzureAccount", name="AzureAccountMocked")
	def test_iteration(self, azure_account):
		# type: (mock.MagicMock) -> None
		azure_account.side_effect = [mock.MagicMock(name="AzureAccount"+str(x)) for x in range(0, self.total_accounts)]
		pool = ConnectionsPool.from_ucr()
		assert len(pool) == self.total_accounts

	@pytest.mark.skip("Not integrated yet")
	@mock.patch("univention.office365.api.account_connector.AzureAccount")
	def test_sub_pool(self, azure_account):
		# type: (mock.MagicMock) -> None
		azure_account.side_effect = [mock.MagicMock(name="AzureAccount"+str(x)) for x in range(0, self.total_accounts)]
		pool = ConnectionsPool.from_ucr()
		sub_pool = pool.sub_pool(["alias1", "alias5"])
		assert len(sub_pool) == 2

	@pytest.mark.skip("Not integrated yet")
	@mock.patch("univention.office365.api.account_connector.UDMHelper", name="UDMHelpertMocked")
	@mock.patch("univention.office365.api.account_connector.AzureAccount", name="AzureAccountMocked")
	def test_create_new(self, azure_account, udm_helper):
		# type: (mock.MagicMock, mock.MagicMock) -> None
		azure_account.side_effect = [mock.MagicMock(name="AzureAccount" + str(x)) for x in range(0, self.total_accounts)]
		pool = ConnectionsPool.from_ucr()
		pool.create_new("alias32", False, restart_listener=False)
		azure_account.create_local.assert_has_calls([mock.call("alias32", lazy_load=True)])

	@pytest.mark.skip("Not integrated yet")
	@mock.patch("univention.office365.api.account_connector.UDMHelper", name="UDMHelpertMocked")
	@mock.patch("univention.office365.api.account_connector.AzureAccount", name="AzureAccountMocked")
	def test_rename(self, azure_account, udm_helper):
		# type: (mock.MagicMock, mock.MagicMock) -> None
		azure_account.side_effect = [mock.MagicMock(name="AzureAccount" + str(x)) for x in range(0, self.total_accounts)]
		pool = ConnectionsPool.from_ucr()
		pool.rename("alias32", "alias33")
		azure_account.create_local.assert_has_calls([mock.call("alias32", lazy_load=True)])

	@pytest.mark.skip("Not integrated yet")
	def test_remove(self):
		# type: () -> None
		assert False
