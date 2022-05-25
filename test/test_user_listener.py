import os

import pytest
from mock import mock
from mock.mock import MagicMock, ANY


class TestUserListener(object):

	@pytest.mark.skipif(not os.path.exists("/tmp/office365/"), reason="Needed files not found")
	def test_handler(self, handler_parameters, office365_usr_lib, initialized_adconnection_default):
		for k,v in handler_parameters.items():
			if v == 'None':
				handler_parameters[k] = {}
		office365_usr_lib.handler(**handler_parameters)

	@pytest.mark.parametrize(
		"disabled, locked, userexpiry, expected_result",
		[
			('0', '0', "2022-03-01", True),
			('0', '0', "2500-03-01", False),
			('0', '0', "___", True),
			('0', '1', "", True),
			('1', '0', "", True),
			('1', '1', "", True),
		]
	)
	def test_is_deactivated_locked_or_expired(self, disabled, locked, userexpiry, expected_result, initialized_adconnection_default, office365_usr_lib):
		udm_user = MagicMock()
		udm_user_info = {'disabled': disabled, 'locked': locked, 'userexpiry': userexpiry}
		udm_user.info.get.side_effect = udm_user_info.get
		assert office365_usr_lib.is_deactivated_locked_or_expired(udm_user) is expected_result

	def test_uninitialized_connections(self, initialized_adconnection_none, office365_usr_lib):
		transaction = ['cn=asdasdasd', {}, {}, "a"]
		with pytest.raises(RuntimeError) as e:
			# Execute the test
			office365_usr_lib.handler(*transaction)

	def test_user_listener_handle_no_old_no_new(self, initialized_adconnection_default, all_user_functions, office365_usr_lib):
		# Configure the test
		transaction = ['cn=asdasdasd', {}, {}, "a"]
		new_user_function, modify_user_function, delete_user_function, deactivate_user_function = all_user_functions

		# Execute the test
		office365_usr_lib.handler(*transaction)
		# Check no operation is done if no new or old
		assert not new_user_function.called
		assert not delete_user_function.called
		assert not deactivate_user_function.called
		assert not modify_user_function.called

	def test_new_user_call(self, initialized_adconnection_default, deactivated_false, all_user_functions, office365_usr_lib):
		transaction = ['cn=asdasdasd', {'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, {}, "a"]
		new_user_function, modify_user_function, delete_user_function, deactivate_user_function = all_user_functions

		with mock.patch.object(office365_usr_lib.listener, "configRegistry", {office365_usr_lib.default_adconnection_alias_ucrv: 'o365domain'}):
			# Execute the test
			office365_usr_lib.handler(*transaction)
			# Check no operation is done if no new or old
			new_user_function.assert_called_once_with(ANY, *transaction[:3])
			assert not delete_user_function.called
			assert not deactivate_user_function.called
			assert not modify_user_function.called

		# Test the case of a user created without ad connection alias
		transaction = ['cn=asdasdasd', {'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': []}, {}, "a"]
		with mock.patch.object(office365_usr_lib.listener, "configRegistry", {office365_usr_lib.default_adconnection_alias_ucrv: 'defaultdomainfortest'}), mock.patch("office365-user.not_migrated_to_v3", False):
			office365_usr_lib.Office365Listener = MagicMock()
			office365_usr_lib.handler(*transaction)
			# check that the correct/default connection is used
			office365_usr_lib.Office365Listener.assert_called_once_with(ANY, ANY, ANY, ANY, transaction[0], 'defaultdomainfortest')

	def test_user_listener_handle_remove_user_from_domain(self, initialized_adconnection_default, deactivated_false, all_user_functions, office365_usr_lib):
		"""
		User is removed from azuretestdomain connection
		A call to delete_user is made to remove the user from the azuretestdomain connection
		A call to modify_user is made to because the user have been modified
		"""
		transaction = ['cn=asdasdasd', {'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, {'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain', b'azuretestdomain']}, "m"]
		new_user_function, modify_user_function, delete_user_function, deactivate_user_function = all_user_functions

		with mock.patch.object(office365_usr_lib.listener, "configRegistry", {office365_usr_lib.default_adconnection_alias_ucrv: 'o365domain'}):
			# Execute the test
			office365_usr_lib.handler(*transaction)
			# Check no operation is done if no new or old
			assert not new_user_function.called
			delete_user_function.assert_called_once_with(ANY, *transaction[:3])
			assert not deactivate_user_function.called
			modify_user_function.assert_called_once_with(ANY, *transaction[:3])

	def test_modify_user_call(self, initialized_adconnection_default, deactivated_false, modify_user_function, office365_usr_lib):
		"""
		Test remove_add_operations
		"""
		# Create params for remove operation for handle
		transaction = ['cn=asdasdasd', {'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, {'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, "r"]
		# call handle
		office365_usr_lib.handler(*transaction)
		delayed = office365_usr_lib._delay
		assert delayed == transaction[2]
		# params for add operation for handle
		transaction = ['cn=otherthing', {'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, {'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, "a"]
		# call handle
		office365_usr_lib.handler(*transaction)
		# Check that deactivate_user is called with _delay content
		expected_arguments = [ANY, 'cn=otherthing', {'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, delayed]
		modify_user_function.assert_called_with(*expected_arguments)

	def test_deactivate_user_call(self, initialized_adconnection_default, office365_usr_lib):
		"""
			if new and not new_enabled:
		"""
		# Create params for remove operation for handle
		transaction = ['cn=asdasdasd', {'univentionOffice365Enabled': [b'0'], 'uid': [b'asdasdasd'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, {"justfortest": 2, 'univentionOffice365Enabled': [b'1'], 'uid': [b'asdasdasd'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, "m"]
		office365_usr_lib.deactivate_user = MagicMock()
		# call handle
		office365_usr_lib.handler(*transaction)
		# check that deactivate_user is called
		office365_usr_lib.deactivate_user.assert_called_once_with(ANY, *transaction[:3])

	def test_delete_user_call(self, initialized_adconnection_default, deactivated_false, delete_user_function, office365_usr_lib):
		"""
		Test the handle function in the situation of needing to call delete user
		No delete user method is currently called
		"""
		"""
			if new and not new_enabled:
		"""
		# Create params for remove operation for handle
		transaction = ['cn=asdasdasd', {}, {"justfortest": 2, 'univentionOffice365Enabled': [b'1'], 'uid': [b'asdasdasd'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}, "m"]

		# call handle
		office365_usr_lib.handler(*transaction)
		# check that deactivate_user is called
		delete_user_function.assert_called_once_with(ANY, *transaction[:3])

	def test_modify_user_function_not_migrated(self, function_params_01, office365_usr_lib):
		"""
		Test the modify function
		"""
		ol, dn, new, old = function_params_01

		# not migrated
		with mock.patch("office365-user.not_migrated_to_v3", True):
			office365_usr_lib.modify_user(*function_params_01)
			ol.modify_user.assert_called_with(*reversed(function_params_01[2:]))
			ol.udm.get_udm_user.assert_called_once_with(function_params_01[1])
			ol.get_user(function_params_01[3])
			ol.udm.get_udm_user.return_value.modify.assert_called_once_with()

	def test_modify_user_function_migrated(self, function_params_01, office365_usr_lib, udm_fake_user_old_listener):
		ol, dn, new, old = function_params_01
		# migrated
		with mock.patch("office365-user.not_migrated_to_v3", False), \
				mock.patch.object(ol, "get_user", return_value={'objectId': '123', 'userPrincipalName': 'oneprincipalname'}), \
				mock.patch.object(ol, "udm.get_udm_user", return_value=udm_fake_user_old_listener):
			office365_usr_lib.modify_user(*function_params_01)
			ol.modify_user.assert_called_once_with(*reversed(function_params_01[2:]))
			ol.udm.get_udm_user.assert_called_once_with(function_params_01[1])
			ol.get_user(function_params_01[3])
			ol.udm.get_udm_user.return_value.modify.assert_called_once_with()

	def test_new_or_reactivate_user_migrated(self, function_params_01, udm_fake_user_old_listener, office365_usr_lib):
		ol, _, new, _ = function_params_01
		with mock.patch("office365-user.not_migrated_to_v3", False), \
				mock.patch.object(ol, "get_user", return_value={'objectId': '123', 'userPrincipalName': 'oneprincipalname'}), \
				mock.patch.object(ol.udm, "get_udm_user", return_value=udm_fake_user_old_listener) as mock_udm_user:
			office365_usr_lib.new_or_reactivate_user(*function_params_01)
			ol.create_user.assert_called_once_with(new)
			ol.udm.get_udm_user.assert_called_once_with(function_params_01[1])
			udm_fake_user_old_listener.modify.assert_called_once_with()
			ol.udm.get_udm_group.assert_called_with(udm_fake_user_old_listener['groups'][0])

	def test_new_or_reactivate_user_not_migrated(self, function_params_01, udm_fake_user_old_listener, office365_usr_lib):
		ol, _, new, _ = function_params_01
		with mock.patch("office365-user.not_migrated_to_v3", True), \
				mock.patch.object(ol, "get_user", return_value={'objectId': '123', 'userPrincipalName': 'oneprincipalname'}), \
				mock.patch.object(ol.udm, "get_udm_user", return_value=udm_fake_user_old_listener) as mock_udm_user:
			office365_usr_lib.new_or_reactivate_user(*function_params_01)
			ol.create_user.assert_called_once_with(new)
			ol.udm.get_udm_user.assert_called_once_with(function_params_01[1])
			office365_usr_lib.Office365Listener.decode_o365data.assert_called()
			udm_fake_user_old_listener.modify.assert_called_once_with()
			udm_fake_user_old_listener.__setitem__.assert_called_with("UniventionOffice365Data", ANY)
			ol.udm.get_udm_group.assert_called_with(udm_fake_user_old_listener['groups'][0])
			ol.create_groups.assert_called_once_with(udm_fake_user_old_listener['groups'][0], ANY)

	def test_delete_user(self, office365_usr_lib):
		ol = MagicMock()
		dn = "asdfasdf"
		new = {'uid': [b'justforTest'], 'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}
		old = {'uid': [b'justforTest2'], 'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}
		params = [ol, dn, new, old]
		office365_usr_lib.delete_user(*params)

	def test_deactivate_user(self, office365_usr_lib):
		ol = MagicMock()
		dn = "asdfasdf"
		new = {'uid': [b'justforTest'], 'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}
		old = {'uid': [b'justforTest2'], 'univentionOffice365Enabled': [b'1'], 'univentionOffice365ADConnectionAlias': [b'o365domain']}
		params = [ol, dn, new, old]
		office365_usr_lib.deactivate_user(*params)
