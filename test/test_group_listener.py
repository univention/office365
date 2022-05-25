import pytest
from mock import mock
from mock.mock import MagicMock, ANY


class TestGroupListener(object):

	def test_uninitialized_connections(self, initialized_adconnection_none, office365_group_lib):
		transaction = ['cn=asdasdasd', {}, {}, "a"]
		with pytest.raises(RuntimeError) as e:
			# Execute the test
			office365_group_lib.handler(*transaction)

	def test_handler_create(self, group_initialized_adconnection_default, office365_group_lib):
		transaction = ['cn=asdasdasd',
					{"justfortest": 2, 'univentionOffice365Enabled': [b'1'], 'uid': [b'asdasdasd'], 'univentionOffice365ADConnectionAlias': [b'o365domain']},
					{},
					"m"]

		office365_group_lib.Office365Listener = MagicMock()
		office365_group_lib.handler(*transaction)

		office365_group_lib.Office365Listener.return_value.create_groups.assert_called_with(transaction[0], transaction[1])

	def test_handler_delete(self, group_initialized_adconnection_default, office365_group_lib):
		transaction = ['cn=asdasdasd',
					{},
					{"justfortest": 2, 'univentionOffice365Enabled': [b'1'], 'uid': [b'asdasdasd'], 'univentionOffice365ADConnectionAlias': [b'o365domain']},
					"m"]

		office365_group_lib.Office365Listener = MagicMock()
		office365_group_lib.handler(*transaction)
		office365_group_lib.Office365Listener.return_value.delete_group.assert_called_with(transaction[2])

	def test_handler_modify(self, group_initialized_adconnection_default, office365_group_lib):
		transaction = ['cn=asdasdasd',
					{'cn': [b'asdasdasd'], "justfortest": 2, 'univentionOffice365Enabled': [b'1'], 'uid': [b'asdasdasd'], 'univentionOffice365ADConnectionAlias': [b'o365domain']},
					{'cn': [b'asdasdasd'], "justfortest": 2, 'univentionOffice365Enabled': [b'1'], 'uid': [b'asdasdasd'], 'univentionOffice365ADConnectionAlias': [b'o365domain']},
					"m"]

		office365_group_lib.Office365Listener = MagicMock()
		office365_group_lib.Office365Listener.return_value.udm.group_in_azure.return_value = True
		office365_group_lib.Office365Listener.return_value.modify_group.return_value = {"objectId": "test_id"}
		office365_group_lib.Office365Listener.return_value.udm.get_udm_group.return_value = "test_udm_group"

		office365_group_lib.handler(*transaction)

		office365_group_lib.Office365Listener.return_value.modify_group.assert_called_with(transaction[2], transaction[1])
		office365_group_lib.Office365Listener.return_value.udm.get_udm_group.assert_called_with(transaction[0])
		office365_group_lib.Office365Listener.return_value.set_adconnection_object_id.assert_called_with("test_udm_group", "test_id")

	def test_handler_modify_has_no_members(self, group_initialized_adconnection_default, office365_group_lib):
		transaction = ['cn=asdasdasd',
					{'cn': [b'asdasdasd'], "justfortest": 2, 'univentionOffice365Enabled': [b'1'], 'uid': [b'asdasdasd'], 'univentionOffice365ADConnectionAlias': [b'o365domain']},
					{'cn': [b'asdasdasd'], "justfortest": 2, 'univentionOffice365Enabled': [b'1'], 'uid': [b'asdasdasd'], 'univentionOffice365ADConnectionAlias': [b'o365domain']},
					"m"]

		office365_group_lib.Office365Listener = MagicMock()
		office365_group_lib.Office365Listener.return_value.udm.group_in_azure.return_value = False
		office365_group_lib.Office365Listener.return_value.modify_group.return_value = {"objectId": "test_id"}
		office365_group_lib.Office365Listener.return_value.udm.get_udm_group.return_value = "test_udm_group"

		office365_group_lib.handler(*transaction)

		office365_group_lib.Office365Listener.return_value.modify_group.assert_called_with(transaction[2], transaction[1])
		office365_group_lib.Office365Listener.return_value.udm.get_udm_group.assert_called_with(transaction[0])
		office365_group_lib.Office365Listener.return_value.set_adconnection_object_id.assert_called_with("test_udm_group", "test_id")
