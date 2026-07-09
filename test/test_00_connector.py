# -*- coding: utf-8 -*-
#
# Univention Office 365 - test_00_connector
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

import sys
from unittest.mock import ANY, call

import mock
import pytest
from typing import Callable

import univention.office365.microsoft
from test import DOMAIN_PATH

from test.utils import all_methods_called

univention.office365.microsoft.OFFICE365_API_PATH = DOMAIN_PATH

fake_module = mock.MagicMock()
sys.modules['univention.debug'] = fake_module
univention.debug = fake_module
sys.modules['lazy_object_proxy'] = mock.MagicMock()
sys.modules['univention.config_registry'] = mock.MagicMock()
pwd_module = mock.MagicMock()
m = mock.Mock()
m.pw_uid = 1000
pwd_module.getpwnam.return_value = m
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

# Mocking grp.getgrnam("nogroup").gr_gid
grp_module = mock.MagicMock()
m = mock.Mock()
m.gr_gid = 1000
grp_module.getgrnam.return_value = m
sys.modules['grp'] = grp_module
sys.modules['univention.lib.i18n'] = mock.MagicMock()
import univention.office365.connector.connector

univention.office365.connector.connector.filter_format = lambda x, y: x % y
from univention.office365.connector.connector import UserConnector, GroupConnector, ConnectorAttributes, UCRHelper, SubscriptionProfile
from univention.office365.microsoft.objects.azureobjects import UserAzure, GroupAzure
from univention.office365.udmwrapper.udmobjects import UniventionOffice365Data
from univention.office365.microsoft.exceptions.core_exceptions import ItemNotFound, MSGraphError
UCRHelper.get_adconnection_filtered_in = mock.MagicMock(return_value=[])
# UCRHelper["office365/subscriptions/service_plan_names"] = None
UCRHelper.get_service_plan_names = mock.MagicMock(
    return_value=[spn.strip() for spn in 'SHAREPOINTWAC, SHAREPOINTWAC_DEVELOPER, OFFICESUBSCRIPTION, OFFICEMOBILE_SUBSCRIPTION, SHAREPOINTWAC_EDU'.split(',')]
)


# "office365/attributes/mapping/l=city",
# "office365/attributes/mapping/displayName=displayName",
# "office365/attributes/mapping/employeeType=jobTitle",
# "office365/attributes/mapping/givenName=givenName",
# "office365/attributes/mapping/mobile=mobilePhone",
# "office365/attributes/mapping/mail=otherMails",
# "office365/attributes/mapping/mailAlternativeAddress=otherMails",
# "office365/attributes/mapping/mailPrimaryAddress=otherMails",
# "office365/attributes/mapping/postalCode=postalCode",
# "office365/attributes/mapping/roomNumber=officeLocation",
# "office365/attributes/mapping/c=usageLocation",
# "office365/attributes/mapping/street=streetAddress",
# "office365/attributes/mapping/sn=surname",
# "office365/attributes/mapping/telephoneNumber=businessPhones",
# "office365/attributes/sync=l,c,displayName,employeeType,givenName,mailPrimaryAddress,mobile,mailAlternativeAddress,mail,postalCode,roomNumber,c,street,sn,telephoneNumber",
# "office365/attributes/anonymize=givenName,street,postalCode",
# "office365/attributes/never=mail,postalCode",
# "office365/attributes/static/roomNumber={}".format(roomNumber),
# "office365/attributes/static/postalCode=12345",
# "office365/attributes/static/l={}".format(city),
# "office365/debug/werror=yes",


@pytest.fixture(scope='function')
def ucr_helper():
    # type: () -> None
    with mock.patch('univention.office365.connector.connector.UCRHelper') as ucr_helper:
        ucr_helper.ucr_split_value.side_effect = [
            ['givenName', 'street', 'postalCode'],
            ['mail', 'postalCode'],
            [
                'l',
                'c',
                'displayName',
                'employeeType',
                'givenName',
                'mailPrimaryAddress',
                'mobile',
                'mailAlternativeAddress',
                'mail',
                'postalCode',
                'roomNumber',
                'c',
                'street',
                'sn',
                'telephoneNumber',
            ],
        ]
        ucr_helper.ucr_entries_to_dict.side_effect = [
            {
                'l': 'city',
                'displayName': 'displayName',
                'employeeType': 'jobTitle',
                'givenName': 'givenName',
                'mobile': 'mobilePhone',
                'mail': 'otherMails',
                'mailAlternativeAddress': 'otherMails',
                'mailPrimaryAddress': 'otherMails',
                'postalCode': 'postalCode',
                'roomNumber': 'officeLocation',
                'c': 'usageLocation',
                'street': 'streetAddress',
                'sn': 'surname',
                'telephoneNumber': 'businessPhones',
            },
            {
                'roomNumber': 'asdf',
                'postalCode': 'asdf',
                'l': 'asdf',
            },
        ]
        yield ucr_helper


class TestConnectorAttributes:
    def test_completity(self):
        # type: () -> None
        assert all_methods_called(TestConnectorAttributes, ConnectorAttributes, [])

    def test___init__(self):
        # type: () -> None
        a = ConnectorAttributes()
        assert a == {}

    def test_all(self, ucr_helper):
        # type: (mock.MagicMock) -> None
        a = ConnectorAttributes()
        assert a.all_sync_keys == {
            'displayName',
            'employeeType',
            'l',
            'mailAlternativeAddress',
            'mailPrimaryAddress',
            'mobile',
            'roomNumber',
            'sn',
            'c',
            'telephoneNumber',
            'givenName',
            'street',
        }

    def test_update_attributes_from_ucr(self, ucr_helper):
        # type: (mock.MagicMock) -> None
        a = ConnectorAttributes(lazy_load=True)
        a.update_attributes_from_ucr()
        assert a.anonymize == {'givenName', 'street', 'postalCode'}
        assert a.never == {'mail', 'postalCode'}
        assert a.sync == {
            'l',
            'c',
            'displayName',
            'employeeType',
            'givenName',
            'mailPrimaryAddress',
            'mobile',
            'mailAlternativeAddress',
            'mail',
            'postalCode',
            'roomNumber',
            'c',
            'street',
            'sn',
            'telephoneNumber',
        }
        assert a.static == {'roomNumber': 'asdf', 'postalCode': 'asdf', 'l': 'asdf'}
        assert a.mapping == {
            'l': 'city',
            'displayName': 'displayName',
            'employeeType': 'jobTitle',
            'givenName': 'givenName',
            'mobile': 'mobilePhone',
            'mail': 'otherMails',
            'mailAlternativeAddress': 'otherMails',
            'mailPrimaryAddress': 'otherMails',
            'postalCode': 'postalCode',
            'roomNumber': 'officeLocation',
            'c': 'usageLocation',
            'street': 'streetAddress',
            'sn': 'surname',
            'telephoneNumber': 'businessPhones',
        }
        assert a.multiple == {'otherMails': ['mail', 'mailAlternativeAddress', 'mailPrimaryAddress']}

    def test__sanitize(self, ucr_helper):
        # type: (mock.MagicMock) -> None
        a = ConnectorAttributes(lazy_load=True)
        a.update_attributes_from_ucr()
        invalid_attributes = ['justfortest', 'univentionOffice365ObjectID', 'UniventionOffice365Data']
        a.sync.update(invalid_attributes)
        a._sanitize()
        assert all([attr not in a.sync for attr in invalid_attributes])

    def test__disjoint_attributes(self, ucr_helper):
        # type: (mock.MagicMock) -> None
        a = ConnectorAttributes(lazy_load=True)
        # Mixing attributes in several sets
        a.update_attributes_from_ucr()
        a.anonymize.update(['mailPrimaryAddress', 'displayName'])
        a.never.update(['displayName', 'postalCode'])
        a._sanitize()
        a._disjoint_attributes()
        assert all([attr not in a.static for attr in a.never])
        assert all([attr not in a.anonymize for attr in a.never])
        assert all([attr not in a.sync for attr in a.anonymize])


class TestUserConnector:
    def setup_method(self):
        # type: () -> None
        self.uc = UserConnector({'o365domain': 'initialized'})
        _attrs = {
            'anonymize': set(),
            'listener': {
                'displayName',
                'employeeType',
                'givenName',
                'krb5KDCFlagskrb5PasswordEnd',
                'krb5ValidEnd',
                'l',
                'mail',
                'mailAlternativeAddress',
                'mailPrimaryAddress',
                'mobile',
                'passwordexpiry',
                'postalCode',
                'roomNumber',
                'sambaAcctFlags',
                'sambaKickoffTime',
                'shadowExpire',
                'shadowLastChange',
                'shadowMax',
                'sn',
                'c',
                'street',
                'telephoneNumber',
                'univentionMicrosoft365Team',
                'univentionOffice365ADConnectionAlias',
                'univentionOffice365Enabled',
                'userPassword',
                'userexpiry',
            },
            'mapping': {
                'displayName': 'displayName',
                'employeeType': 'jobTitle',
                'givenName': 'givenName',
                'l': 'city',
                'mail': 'otherMails',
                'mailAlternativeAddress': 'otherMails',
                'mailPrimaryAddress': 'otherMails',
                'mobile': 'mobilePhone',
                'postalCode': 'postalCode',
                'roomNumber': 'officeLocation',
                'sn': 'surname',
                'c': 'usageLocation',
                'street': 'streetAddress',
                'telephoneNumber': 'businessPhones',
            },
            'never': set(),
            'static': set(),
            'sync': {
                'displayName',
                'employeeType',
                'givenName',
                'l',
                'mail',
                'mailAlternativeAddress',
                'mailPrimaryAddress',
                'mobile',
                'postalCode',
                'roomNumber',
                'sn',
                'c',
                'street',
                'telephoneNumber',
            },
            'multiple': {'otherMails': ['mail', 'mailAlternativeAddress', 'mailPrimaryAddress']},
        }
        for key, value in _attrs.items():
            setattr(self.uc.attrs, key, value)

        alias = 'o365domain'
        domain = 'o365domain.onmicrosoft.com'
        core = mock.MagicMock(account=mock.MagicMock(data={'domain': domain}, alias=alias))
        self.uc._cores = {alias: core}

    def test_completity(self):
        # type: () -> None
        diff = all_methods_called(self.__class__, UserConnector, ['anonymize_attr', '_load_filtered_accounts'])
        assert len(diff) == 0, 'Functions no tested [' + ', '.join(diff) + ']'

    def test_connector_init(self):
        # type: () -> None
        assert self.uc

    def test_get_listener_filter(self):
        # type: () -> None
        """"""
        self.uc.filtered_in_aliases = ['o365domain']
        assert self.uc.get_listener_filter() == '(univentionOffice365ADConnectionAlias=o365domain)'

    def test_get_core(self):
        assert self.uc.get_core('wrong_alias') == None
        assert self.uc.get_core('o365domain')

    def test_parse(self, create_udm_user_object):
        # type: (Callable) -> None
        udm_fake_user = create_udm_user_object()

        domain = 'o365domain.onmicrosoft.com'
        core = mock.MagicMock(account={'domain': domain})
        azure_user = self.uc.parse(udm_fake_user, core)
        assert azure_user.get_not_none_values_as_dict()['displayName'] == udm_fake_user.displayName
        assert azure_user.get_not_none_values_as_dict()['userPrincipalName'] == udm_fake_user.displayName + '@' + domain
        assert azure_user.get_not_none_values_as_dict()['onPremisesImmutableId'] == udm_fake_user.entryUUID
        assert azure_user.get_not_none_values_as_dict()['surname'] == udm_fake_user.sn

    # @pytest.mark.skip("Not needed anymore")
    # def test_invalidate_all_tokens(self):
    # 	# type: () -> None
    # 	self.uc._invalidate_all_tokens()

    def test__assign_subscription(self, create_udm_user_object, ucr_helper):
        # type: (Callable, mock.MagicMock) -> None
        udm_fake_user = create_udm_user_object()
        subscription = mock.MagicMock()
        subscription.subscription = 'TEAMS_EXPLORATORY'

        SubscriptionProfile.get_profiles_for_groups = mock.MagicMock(return_value=[subscription])
        # subs_available = SubscriptionAzure.get_enabled(self.cores[udm_object.current_connection_alias], UCRHelper.get_service_plan_names())
        subs_available = [mock.MagicMock(skuPartNumber='TEAMS_EXPLORATORY')]
        for _ in udm_fake_user.aliases():
            azure_user = mock.MagicMock(spec=UserAzure, autospec=True)
            azure_user.id = '1234567890'
            self.uc._assign_subscription(udm_fake_user, azure_user, self.uc.logger, subs_available)
            azure_user.add_license.assert_called_once()

    def test_prepare_azure_attributes(self):
        # type: () -> None
        azure_user = mock.MagicMock(spec=UserAzure, autospec=True)
        azure_user.id = '1234567890'
        azure_user.userPrincipalName = 'name'
        result = self.uc.prepare_azure_attributes(azure_user)
        assert result['objectId'] == azure_user.id
        assert result['userPrincipalName'] == azure_user.userPrincipalName

    def test_new_or_reactivate_user(self, create_udm_user_object):
        # type: (Callable) -> None

        alias = 'o365domain'
        domain = 'o365domain.onmicrosoft.com'
        core = mock.MagicMock(account=mock.MagicMock(data={'domain': domain}, alias=alias))

        udm_fake_user = create_udm_user_object()
        udm_fake_user.current_connection_alias = 'o365domain'
        udm_fake_user.modify_azure_attributes = mock.MagicMock()
        azure_user = mock.MagicMock()
        azure_user.id = '1234567890'
        azure_user.userPrincipalName = 'name'
        self.uc.parse = mock.MagicMock(side_effect=[azure_user, mock.MagicMock()])
        self.uc._assign_subscription = mock.MagicMock()
        self.uc.prepare_azure_attributes = mock.MagicMock(return_value={})
        self.uc.group_connector = mock.MagicMock()
        with mock.patch('univention.office365.connector.connector.SubscriptionAzure', mock.MagicMock()):
            self.uc.new_or_reactivate_user(udm_fake_user, core)
            self.uc.parse.assert_called_once()
            azure_user.create_or_modify.assert_called_once()
            azure_user.invalidate_all_tokens()
            udm_fake_user.modify_azure_attributes.assert_called_once()

    def test_create(self, create_udm_user_object):
        # type: (Callable) -> None
        udm_fake_user = create_udm_user_object()
        self.uc.new_or_reactivate_user = mock.MagicMock()
        self.uc.get_core = mock.MagicMock()
        self.uc.create(udm_fake_user)
        # new_or_reactivate_user is called as many times as there are aliases
        self.uc.new_or_reactivate_user.assert_has_calls([mock.call(ANY, ANY)] * len(list(udm_fake_user.aliases())))

    def test_delete(self, create_udm_user_object):
        # type: (Callable) -> None
        udm_fake_user = create_udm_user_object()
        udm_fake_user.modify_azure_attributes = mock.MagicMock()
        azure_user = mock.MagicMock()
        azure_user.get_not_none_values_as_dict.return_value = {'displayName': 'test', 'uid': 'testuid', 'objectId': 'testobjectid'}
        self.uc.parse = mock.MagicMock(side_effect=[azure_user, mock.MagicMock()])
        self.uc.delete(udm_fake_user)
        azure_user.deactivate.assert_called_once()

    def test_deactivate(self, create_udm_user_object):
        # type: (Callable) -> None
        udm_fake_user = create_udm_user_object()
        udm_fake_user.modify_azure_attributes = mock.MagicMock()
        azure_user = mock.MagicMock()
        self.uc.parse = mock.MagicMock(side_effect=[azure_user, mock.MagicMock()])
        self.uc.delete(udm_fake_user)
        azure_user.deactivate.assert_called_once()

    def test_modify(self, create_udm_user_object):
        # type: (Callable) -> None
        azure_user_new = mock.MagicMock()
        azure_user_old = mock.MagicMock()
        azure_user_old.assert_id = mock.MagicMock(return_value=True)
        self.uc.parse = mock.MagicMock(side_effect=[azure_user_old, azure_user_new, mock.MagicMock()])

        # Test users with modified alias for NEW or REACTIVATED account
        # Modify o365domain and add otherconn
        udm_fake_user_old = create_udm_user_object()
        udm_fake_user_new = create_udm_user_object()
        udm_fake_user_new.modify_azure_attributes = mock.MagicMock()
        self.uc.new_or_reactivate_user = mock.MagicMock()
        self.uc._cores['otherconn'] = mock.MagicMock()
        udm_fake_user_old.udm_object_reference['UniventionOffice365ADConnectionAlias'] = ['o365domain']
        udm_fake_user_new.udm_object_reference['UniventionOffice365ADConnectionAlias'] = ['o365domain', 'otherconn']
        self.uc.modify(udm_fake_user_old, udm_fake_user_new)
        self.uc.new_or_reactivate_user.assert_called_once()
        azure_user_old.update.assert_called_with(azure_user_new)
        udm_fake_user_new.modify_azure_attributes.assert_called_once()
        assert self.uc.parse.call_count == 2

        # Test removed connections
        # Remove otherconn1	from aliases and modify o365domain and otherconn2
        udm_fake_user_old = create_udm_user_object()
        udm_fake_user_new = create_udm_user_object()
        udm_fake_user_new.modify_azure_attributes = mock.MagicMock()
        self.uc.get_core = mock.MagicMock()
        udm_fake_user_old.udm_object_reference['UniventionOffice365ADConnectionAlias'] = ['o365domain', 'otherconn1', 'otherconn2']
        udm_fake_user_new.udm_object_reference['UniventionOffice365ADConnectionAlias'] = ['o365domain', 'otherconn2']
        self.uc.parse = mock.MagicMock(side_effect=[azure_user_old, azure_user_old, azure_user_new, azure_user_old, azure_user_new, mock.MagicMock()])

        self.uc.modify(udm_fake_user_old, udm_fake_user_new)
        assert self.uc.parse.call_count == 5

        azure_user_old.deactivate.assert_called_once()
        # One call for remove, two calls for modifications
        assert udm_fake_user_new.modify_azure_attributes.call_count == 3

        # Test modified connections
        # Modify attributes in the 3 connections
        udm_fake_user_old = create_udm_user_object()
        udm_fake_user_new = create_udm_user_object()
        udm_fake_user_new.udm_object_reference['UniventionOffice365ADConnectionAlias'] = ['o365domain', 'otherconn1', 'otherconn2']
        udm_fake_user_old.udm_object_reference['UniventionOffice365ADConnectionAlias'] = ['o365domain', 'otherconn1', 'otherconn2']
        udm_fake_user_new.modify_azure_attributes = mock.MagicMock()
        self.uc.parse = mock.MagicMock(side_effect=[azure_user_old, azure_user_new, azure_user_old, azure_user_new, azure_user_old, azure_user_new])
        udm_fake_user_new.street = 'other_street'
        self.uc.modify(udm_fake_user_old, udm_fake_user_new)
        # One call for each connection
        assert udm_fake_user_new.modify_azure_attributes.call_count == 3

    def test_check_permissions(self):
        # type: () -> None

        alias = 'o365domain'
        get_permissions = mock.MagicMock(
            retunr_value={
                '@odata.context': "https://graph.microsoft.com/v1.0/$metadata#servicePrincipals('d521afe4-7a36-40de-9fcd-a63239268712')/appRoleAssignments(appRoleId)",
                'value': [
                    {'appRoleId': '78c8a3c8-a07e-4b9e-af1b-b5ccab50a175'},
                    {'appRoleId': '741f803b-c850-494e-b5df-cde7c675a1ca'},
                    {'appRoleId': '19dbc75e-c2e2-444c-a770-ec69d8559fc7'},
                    {'appRoleId': '62a82d76-70ea-41e2-9197-370581804d09'},
                    {'appRoleId': '0121dc95-1b9f-4aed-8bac-58c5ac466691'},
                ],
            }
        )
        core = mock.MagicMock(get_permissions=get_permissions)

        self.uc._check_permissions(alias, core)
        core.get_permissions.assert_called_once()


class TestGroupConnector:
    def setup_method(self):
        # type: () -> None
        self.gc = GroupConnector({'o365domain': 'initialized'})
        self.gc.async_task = False

    def test_completity(self):
        # type: () -> None
        diff = all_methods_called(self.__class__, GroupConnector, ['check_permissions', 'get_core'])
        assert len(diff) == 0, 'Functions no tested [' + ', '.join(diff) + ']'

    def test_parse(self, create_udm_group_object):
        # type: (Callable) -> None
        core = mock.MagicMock()

        udm_fake_group = create_udm_group_object()
        udm_fake_group.create_azure_attributes = mock.MagicMock()
        azure_group = self.gc.parse(udm_fake_group, core)
        assert azure_group.displayName == udm_fake_group.cn
        assert azure_group.description == udm_fake_group.description
        assert azure_group.id == udm_fake_group.azure_object_id
        assert azure_group.groupTypes == []
        udm_fake_group.udm_object_reference['UniventionMicrosoft365GroupType'] = 'Microsoft 365 Group'
        azure_group = self.gc.parse(udm_fake_group, core)
        assert azure_group.groupTypes == ['Unified']

    def test_add_ldap_members_to_azure_group(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.current_connection_alias = 'o365domain'
        udm_fake_group.get_users_from_ldap = mock.MagicMock(return_value=['user1', 'user2', 'group1'])
        groups_member_of_not_in_azure = [mock.MagicMock()] * 2
        udm_fake_group.get_groups_member_of_not_in_azure = mock.MagicMock(side_effect=[groups_member_of_not_in_azure])
        self.gc.current_connection_alias = 'o365domain'
        self.gc._create_group = mock.MagicMock()
        nested_group = mock.MagicMock()
        nested_group.azure_object_id = 'nested_id'
        udm_fake_group.get_nested_groups_with_azure_users = mock.MagicMock(return_value=[nested_group])
        core = mock.MagicMock()
        azure_object = mock.MagicMock()
        azure_object.id = 'azure_object_id'
        self.gc.add_ldap_members_to_azure_group(udm_fake_group, azure_object, core)
        # Check add_member is called with the names of the members
        azure_object.add_members.assert_called_once_with(['user1', 'user2', 'group1'])
        # Check the group creation of the members of udm_fake_group not in azure
        self.gc._create_group.assert_has_calls([call(x, core) for x in groups_member_of_not_in_azure])

    def test__create_group(self, create_udm_group_object):
        # type: (Callable) -> None
        alias = 'o365domain'
        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.current_connection_alias = 'o365domain'

        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'
        self.gc.parse = mock.MagicMock(return_value=azure_group)
        self.gc.add_ldap_members_to_azure_group = mock.MagicMock()

        result = self.gc._create_group(udm_fake_group, alias)
        assert result == azure_group
        azure_group.create_or_modify.assert_called_once()
        self.gc.parse.assert_called_once_with(udm_fake_group, alias)
        self.gc.add_ldap_members_to_azure_group.assert_called_once_with(udm_fake_group, azure_group, ANY)

    def test_convert_group_to_team(self, create_udm_group_object):
        # type: (Callable) -> None
        """"""
        alias = 'o365domain'
        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=True)
        udm_fake_group.current_connection_alias = 'o365domain'
        owners = [mock.MagicMock()] * 2
        udm_fake_group.get_owners = mock.MagicMock(return_value=owners)
        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'
        azure_group.resourceProvisioningOptions = []
        with mock.patch('univention.office365.connector.connector.TeamAzure') as mock_team, mock.patch('univention.office365.connector.connector.GroupAzure') as mock_group:
            mock_team.create_from_group = mock.MagicMock()
            mock_group.get = mock.MagicMock(return_value=azure_group)

            self.gc.convert_group_to_team(udm_fake_group, azure_group)
            azure_group.add_owner.assert_has_calls([call(ANY, async_task=False) for x in owners])
            mock_team.create_from_group.assert_called_once_with(ANY, azure_group.id, education_class=False)

    def test_create(self, create_udm_group_object):
        # type: (Callable) -> None
        alias = 'o365domain'
        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=True)
        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'
        core = mock.MagicMock()
        self.gc._cores[alias] = core
        self.gc._create_group = mock.MagicMock(return_value=azure_group)
        self.gc.convert_group_to_team = mock.MagicMock()
        self.gc.create(udm_fake_group)
        self.gc._create_group.assert_called_once_with(udm_fake_group, core)
        self.gc.convert_group_to_team.assert_called_once_with(udm_fake_group, azure_group)

    def test_delete(self, create_udm_group_object):
        # type: (Callable) -> None
        alias = 'o365domain'
        self.gc._cores[alias] = mock.MagicMock()

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=True)
        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'
        self.gc.parse = mock.MagicMock(return_value=azure_group)
        udm_fake_group.udm_object_reference['UniventionOffice365Data'] = UniventionOffice365Data({'o365domain': {'objectId': 'the_object_id'}}).to_ldap_str()
        with mock.patch('univention.office365.connector.connector.TeamAzure') as mock_team:
            self.gc.delete(udm_fake_group)
            mock_team.return_value.deactivate.assert_called_once()
            azure_group.remove_direct_members.assert_called_once()
            azure_group.deactivate.assert_called_once()

    def test_check_and_modify_teams(self, create_udm_group_object):
        alias = 'o365domain'
        self.gc._cores[alias] = mock.MagicMock()
        # type: (Callable) -> None
        udm_fake_group_old = create_udm_group_object()
        udm_fake_group_old.current_connection_alias = alias

        udm_fake_group_new = create_udm_group_object()

        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'
        self.gc.parse = mock.MagicMock(return_value=azure_group)
        self.gc.convert_group_to_team = mock.MagicMock()

        # Check for new team
        udm_fake_group_old.is_team = mock.MagicMock(return_value=False)
        udm_fake_group_new.is_team = mock.MagicMock(return_value=True)

        with mock.patch("univention.office365.connector.connector.TeamAzure") as mock_team:
            mock_team.get.side_effect = ItemNotFound(MSGraphError(None, "message"))
            self.gc.check_and_modify_teams(udm_fake_group_old, udm_fake_group_new, azure_group, alias)
            self.gc.convert_group_to_team.assert_called_once_with(udm_fake_group_new, azure_group)

        # Check reactivate team
        with mock.patch("univention.office365.connector.connector.TeamAzure") as mock_team:
            self.gc.check_and_modify_teams(udm_fake_group_old, udm_fake_group_new, azure_group, alias)
            mock_team.get.return_value.reactivate.assert_called_once()

        # Check deactivate/remove team
        udm_fake_group_old.is_team = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_team = mock.MagicMock(return_value=False)
        with mock.patch("univention.office365.connector.connector.TeamAzure") as mock_team:
            self.gc.check_and_modify_teams(udm_fake_group_old, udm_fake_group_new, azure_group, alias)
            mock_team.get.return_value.deactivate.assert_called_once()

    def test_check_and_modify_owners(self, create_udm_group_object):
        # type: (Callable) -> None
        alias = 'o365domain'
        udm_fake_group_old = create_udm_group_object()
        udm_fake_group_old.current_connection_alias = alias

        udm_fake_group_new = create_udm_group_object()

        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'
        self.gc.parse = mock.MagicMock(return_value=azure_group)

        self.gc.convert_group_to_team = mock.MagicMock()

        # Check owners to add
        old_owners = [mock.MagicMock(dn=dn) for dn in ['uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet']]
        new_owners = old_owners + [mock.MagicMock(dn=dn) for dn in ['uid=newowner,cn=users,dc=test-idelgado-com,dc=intranet']]
        udm_fake_group_old.get_owners = mock.MagicMock(return_value=old_owners)
        udm_fake_group_new.get_owners = mock.MagicMock(return_value=new_owners)
        # udm_fake_group_old.owners_changes = mock.MagicMock()

        self.gc.check_and_modify_owners(udm_fake_group_old, udm_fake_group_new, azure_group, alias)
        azure_group.add_owner.assert_called_once()

        # Check owners to remove
        old_owners = [
            mock.MagicMock(dn=dn, name=dn) for dn in ['uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=ownertoremove,cn=users,dc=test-idelgado-com,dc=intranet']
        ]
        new_owners = old_owners[0:1]
        udm_fake_group_old.get_owners = mock.MagicMock(return_value=old_owners)
        udm_fake_group_new.get_owners = mock.MagicMock(return_value=new_owners)

        self.gc.check_and_modify_owners(udm_fake_group_old, udm_fake_group_new, azure_group, alias)
        azure_group.add_owner.assert_called_once()

    def test_delete_empty_group(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_team = mock.MagicMock(return_value=True)
        udm_fake_group_new.current_connection_alias = 'o365domain'

        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'
        azure_group.list_members = mock.MagicMock()
        azure_group.member_of = mock.MagicMock()

        # Check delete of group with active members
        assert self.gc.delete_empty_group(azure_group, udm_fake_group_new) is False

        # Check delete of group without active members
        azure_group.list_members = mock.MagicMock(return_value=[])
        azure_group.remove_direct_members = mock.MagicMock()
        azure_group.deactivate = mock.MagicMock()

        udm_fake_group_new.deactivate_azure_attributes = mock.MagicMock()

        self.gc.delete_empty_group(azure_group, udm_fake_group_new)
        azure_group.remove_direct_members.assert_called_once()
        azure_group.deactivate.assert_called_once()
        udm_fake_group_new.deactivate_azure_attributes.assert_called_once()

    def test_check_and_modify_members(self, create_udm_group_object):
        # type: (Callable) -> None
        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias
        self.gc._cores[alias] = core

        udm_fake_group_old = create_udm_group_object()
        udm_fake_group_old.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_old.is_team = mock.MagicMock(return_value=True)

        udm_fake_group_old.get_members = mock.MagicMock(
            return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'}
        )

        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_team = mock.MagicMock(return_value=True)

        udm_fake_group_new.get_members = mock.MagicMock(
            return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet', 'uid=onetobeadded,cn=groups,dc=test-idelgado-com,dc=intranet'}
        )

        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'
        azure_group.add_members = mock.MagicMock()
        azure_group.remove_member = mock.MagicMock()
        self.gc.parse = mock.MagicMock(return_value=azure_group)

        # Check for member not in nested groups or users RuntimeError
        with pytest.raises(RuntimeError):
            self.gc.check_and_modify_members(udm_fake_group_old, udm_fake_group_new, azure_group, core)

        # Check member "to add" is user:
        udm_fake_group_old.get_users = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
        udm_fake_group_old.get_nested_group = mock.MagicMock(return_value={'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'})

        udm_fake_group_new.get_users = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
        udm_fake_group_new.get_nested_group = mock.MagicMock(return_value={'uid=onetobeadded,cn=groups,dc=test-idelgado-com,dc=intranet'})
        udm_fake_group_new.current_connection_alias = 'azuretestdomain'

        udm_group = create_udm_group_object()
        udm_group.get_nested_groups_with_azure_users = mock.MagicMock(return_value=[udm_group])
        udm_group.get_nested_group = mock.MagicMock(return_value={'cn=test,dc=test,dc=test'})
        with mock.patch('univention.office365.connector.connector.UDMOfficeGroup', mock.MagicMock(return_value=udm_group)), mock.patch(
            'univention.office365.connector.connector.GroupAzure.get_by_name', mock.MagicMock(return_value=None)
        ), mock.patch('univention.office365.connector.connector.TeamAzure') as mock_team:
            self.gc._cores['azuretestdomain'] = core
            self.gc.check_and_modify_members(udm_fake_group_old, udm_fake_group_new, azure_group, core)
            self.gc._cores.pop('azuretestdomain')
            azure_group.add_members.assert_called_once()
            # azure_group.remove_member.assert_called_once()

        # Check for empty group (removed_members_dn and not added_members_dn)
        self.gc.delete_empty_group = mock.MagicMock()
        azure_group.remove_member = mock.MagicMock()
        udm_fake_group_old.get_users = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
        udm_fake_group_old.get_nested_group = mock.MagicMock(return_value={'uid=onetoremove,cn=groups,dc=test-idelgado-com,dc=intranet'})

        udm_fake_group_new.get_members = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
        udm_fake_group_new.get_users = mock.MagicMock(return_value={'uid=domvzkat0s,cn=users,dc=test-idelgado-com,dc=intranet'})
        udm_fake_group_new.current_connection_alias = 'azuretestdomain'
        with mock.patch('univention.office365.connector.connector.UDMOfficeGroup', mock.MagicMock(return_value=create_udm_group_object())), mock.patch(
            'univention.office365.connector.connector.GroupAzure.get_by_name', mock.MagicMock(return_value=None)
        ):
            self.gc.check_and_modify_members(udm_fake_group_old, udm_fake_group_new, azure_group, core)
            # azure_group.remove_member.assert_called_once()
            self.gc.delete_empty_group.assert_called_once_with(azure_group, udm_fake_group_new)

    def test_check_and_modify_attributes(self, create_udm_group_object):
        # type: (Callable) -> None
        alias = 'o365domain'
        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_team = mock.MagicMock(return_value=True)

        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'

        new_azure_group = mock.MagicMock()
        new_azure_group.id = 'new_azure_object_id'
        self.gc.parse = mock.MagicMock(return_value=new_azure_group)

        self.gc.check_and_modify_attributes(udm_fake_group_new, azure_group, alias)
        azure_group.update.assert_called_once_with(new_azure_group)

    def test_modify(self, create_udm_group_object):
        # type: (Callable) -> None
        alias = 'o365domain'
        udm_fake_group_old = create_udm_group_object()
        udm_fake_group_old.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_old.is_team = mock.MagicMock(return_value=True)

        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_team = mock.MagicMock(return_value=True)
        udm_fake_group_new.modify_azure_attributes = mock.MagicMock()

        azure_group = mock.MagicMock(name='azure_group')
        azure_group.id = 'azure_object_id'
        new_azure_group = mock.MagicMock(name='new_azure_group')
        new_azure_group.id = 'azure_object_id'
        self.gc.parse = mock.MagicMock(side_effect=[new_azure_group])
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        created_group = mock.MagicMock(name='new_create_azure_group')
        created_group.id = 'created_group_object_id'
        created_group.is_security_group = mock.MagicMock(return_value=True)
        created_group.is_delete = mock.MagicMock(return_value=True)
        self.gc._create_group = mock.MagicMock(return_value=created_group)

        # Check no modifications
        self.gc.modify(udm_fake_group_old, udm_fake_group_new)
        udm_fake_group_new.modify_azure_attributes.assert_not_called()

        # Check modifications TODO:
        self.gc._create_group = mock.MagicMock(return_value=created_group)
        self.gc.parse = mock.MagicMock(side_effect=[azure_group, new_azure_group])
        created_group.is_delete = mock.MagicMock(return_value=False)
        udm_fake_group_new.udm_object_reference.oldattr['description'] = b'the new description'
        self.gc.check_and_modify_teams = mock.MagicMock()
        self.gc.check_and_modify_owners = mock.MagicMock()
        self.gc.check_and_modify_members = mock.MagicMock()
        self.gc.check_and_modify_attributes = mock.MagicMock()

        self.gc.modify(udm_fake_group_old, udm_fake_group_new)

        self.gc._create_group.assert_called_once()
        self.gc.check_and_modify_teams.assert_called_once_with(udm_fake_group_old, udm_fake_group_new, created_group, alias)
        self.gc.check_and_modify_owners.assert_called_once_with(udm_fake_group_old, udm_fake_group_new, created_group, alias)
        self.gc.check_and_modify_members.assert_called_once_with(udm_fake_group_old, udm_fake_group_new, created_group, core)
        self.gc.check_and_modify_attributes.assert_called_once_with(udm_fake_group_new, created_group, core)

    def test_migrate_group_type(self, create_udm_group_object):
        # type: (Callable) -> None
        alias = 'o365domain'
        udm_fake_group_old = create_udm_group_object()
        udm_fake_group_old.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_old.is_team = mock.MagicMock(return_value=True)

        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_team = mock.MagicMock(return_value=False)
        udm_fake_group_new.current_connection_alias = alias

        azure_group = mock.MagicMock()
        azure_group.id = 'azure_object_id'
        azure_group.is_delete = mock.MagicMock(return_value=False)
        azure_group.delete = mock.MagicMock()
        self.gc.parse = mock.MagicMock(return_value=azure_group)
        self.gc._create_group = mock.MagicMock()
        self.gc.deactivate = mock.MagicMock()
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        self.gc.migrate_group_type(udm_fake_group_new, azure_group, core)

        self.gc._create_group.assert_called_once()
        azure_group.delete.assert_called_once()

    def test_add_member(self, create_udm_group_object):
        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias
        # type: (Callable) -> None
        udm_fake_user = mock.MagicMock()
        udm_fake_group = create_udm_group_object()
        # udm_fake_group.current_connection_alias = alias
        azure_group = mock.MagicMock()
        self.gc.parse = mock.MagicMock(return_value=azure_group)

        self.gc.add_member(udm_fake_group, udm_fake_user, core)
        self.gc.parse.assert_called_once_with(udm_fake_group, core)
        azure_group.add_member.assert_called_once_with(udm_fake_user.azure_object_id)

    def test_remove_member(self, create_udm_group_object):
        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias
        # type: (Callable) -> None
        alias = 'o365domain'
        udm_fake_user = mock.MagicMock()
        udm_fake_group = create_udm_group_object()
        # udm_fake_group.current_connection_alias = "o365domain"
        azure_group = mock.MagicMock()
        self.gc.parse = mock.MagicMock(return_value=azure_group)

        self.gc.remove_member(udm_fake_group, udm_fake_user, core)
        self.gc.parse.assert_called_once_with(udm_fake_group, core)
        azure_group.remove_member.assert_called_once_with(udm_fake_user.azure_object_id)

    def test_get_listener_filter(self):
        # type: () -> None
        self.gc.filtered_in_aliases = ['o365domain']
        with mock.patch('univention.office365.connector.connector.UCRHelper') as ucr_helper:
            ucr_helper.get_adconnection_filtered_in = mock.MagicMock(return_value=['o365domain'])
            assert self.gc.get_listener_filter() == '(univentionOffice365ADConnectionAlias=o365domain)'

    def test_prepare_azure_attributes(self):
        # type: () -> None
        azure_user = mock.MagicMock(id='test_id', userPrincipalName='test_display_name')
        assert self.gc.prepare_azure_attributes(azure_user) == {'objectId': 'test_id'}

    # ------------------------------------------------------------------
    # Education Class tests
    # ------------------------------------------------------------------

    def test_parse_education_class(self, create_udm_group_object):
        # type: (Callable) -> None
        """parse_education_class() should produce an EducationClassAzure with
        the correct fields taken from the UDM group object.
        externalId must come from univentionObjectIdentifier, not a custom attribute."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure

        core = mock.MagicMock()
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassCode'] = 'CS101'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassGrade'] = 'Grade 5'
        # Simulate the built-in UDM univentionObjectIdentifier attribute
        test_uuid = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
        udm_fake_group.udm_object_reference.oldattr['univentionObjectIdentifier'] = [test_uuid.encode('ASCII')]

        edu_class = self.gc.parse_education_class(udm_fake_group, core)

        assert isinstance(edu_class, EducationClassAzure)
        assert edu_class.displayName == udm_fake_group.cn
        assert edu_class.classCode == 'CS101'
        assert edu_class.externalId == test_uuid
        assert edu_class.grade == 'Grade 5'

    def test__create_education_class(self, create_udm_group_object):
        # type: (Callable) -> None
        """_create_education_class() should call create_or_modify, write back
        the Azure ID to UDM, add teachers, and add members."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure, GroupAzure

        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias

        udm_fake_group = create_udm_group_object()
        udm_fake_group.current_connection_alias = alias
        udm_fake_group.get_owners = mock.MagicMock(return_value=[])
        udm_fake_group.modify_azure_attributes = mock.MagicMock()

        edu_class_mock = mock.MagicMock(spec=EducationClassAzure)
        edu_class_mock.id = 'edu-class-azure-id'

        group_azure_mock = mock.MagicMock(spec=GroupAzure)
        group_azure_mock.id = 'edu-class-azure-id'
        group_azure_mock.is_security_group.return_value = False
        group_azure_mock.visibility = None

        self.gc.parse_education_class = mock.MagicMock(return_value=edu_class_mock)
        self.gc.parse = mock.MagicMock(return_value=group_azure_mock)
        self.gc.add_ldap_members_to_azure_group = mock.MagicMock()

        result = self.gc._create_education_class(udm_fake_group, core)

        assert isinstance(result, GroupAzure)
        assert result.id == 'edu-class-azure-id'
        edu_class_mock.create_or_modify.assert_called_once()
        udm_fake_group.modify_azure_attributes.assert_called_once()
        self.gc.add_ldap_members_to_azure_group.assert_called_once()

    def test__create_education_class_falls_back_to_m365_group_on_error(self, create_udm_group_object):
        # type: (Callable) -> None
        """When the Education Roster API raises MSGraphError, _create_education_class()
        must fall back to creating a regular Microsoft 365 group via _create_group()."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure
        from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError

        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias

        udm_fake_group = create_udm_group_object()
        udm_fake_group.current_connection_alias = alias
        udm_fake_group.get_owners = mock.MagicMock(return_value=[])
        udm_fake_group.modify_azure_attributes = mock.MagicMock()

        # Simulate an API failure during education class creation
        edu_class_mock = mock.MagicMock(spec=EducationClassAzure)
        edu_class_mock.create_or_modify.side_effect = MSGraphError(mock.MagicMock(status_code=403), 'Edu API not available')

        fallback_group = mock.MagicMock()
        fallback_group.id = 'm365-group-id'

        self.gc.parse_education_class = mock.MagicMock(return_value=edu_class_mock)
        self.gc._create_group = mock.MagicMock(return_value=fallback_group)
        self.gc.add_ldap_members_to_azure_group = mock.MagicMock()

        result = self.gc._create_education_class(udm_fake_group, core)

        # Should have attempted the Education API
        edu_class_mock.create_or_modify.assert_called_once()
        # Should have fallen back to the regular group path
        self.gc._create_group.assert_called_once_with(udm_fake_group, core)
        # The returned object is the fallback group
        assert result is fallback_group
        # UDM attributes should NOT have been written for the education class
        udm_fake_group.modify_azure_attributes.assert_not_called()

    def test_create_education_class_route(self, create_udm_group_object):
        # type: (Callable) -> None
        """GroupConnector.create() calls _create_education_class() directly
        when the group is an Education Class."""
        alias = 'o365domain'
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)

        edu_class_mock = mock.MagicMock()
        edu_class_mock.id = 'edu-class-azure-id'
        edu_class_mock.displayName = 'TestClass'
        self.gc._create_education_class = mock.MagicMock(return_value=edu_class_mock)
        self.gc._create_group = mock.MagicMock()

        self.gc.create(udm_fake_group)

        # create() calls _create_education_class() directly for Education Class groups
        self.gc._create_education_class.assert_called_once()
        self.gc._create_group.assert_not_called()

    def test_delete_education_class_route(self, create_udm_group_object):
        # type: (Callable) -> None
        """GroupConnector.delete() currently uses the regular group deactivation
        path for education classes (the Education-specific path is commented out).
        Verify the group is deactivated via the standard path."""
        alias = 'o365domain'
        self.gc._cores[alias] = mock.MagicMock()

        udm_fake_group = create_udm_group_object()
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group.udm_object_reference['UniventionOffice365Data'] = UniventionOffice365Data(
            {'o365domain': {'objectId': 'edu-class-azure-id'}}
        ).to_ldap_str()

        azure_group = mock.MagicMock()
        self.gc.parse = mock.MagicMock(return_value=azure_group)

        self.gc.delete(udm_fake_group)

        # Education class path is commented out, so it uses regular group deactivation
        azure_group.remove_direct_members.assert_called_once()
        azure_group.deactivate.assert_called_once()

    def test_migrate_group_type_to_education_class(self, create_udm_group_object):
        # type: (Callable) -> None
        """migrate_group_type() should use _create_education_class() as
        the recreation step when the target type is Education Class."""
        alias = 'o365domain'
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        # Patch azure_object_id as a property to return None (no existing ID -> skip delete branch)
        type(udm_fake_group).azure_object_id = mock.PropertyMock(return_value=None)

        azure_group = mock.MagicMock()
        azure_group.is_delete = mock.MagicMock(return_value=True)  # already deactivated

        edu_class_mock = mock.MagicMock()
        edu_class_mock.id = 'new-edu-id'
        edu_class_mock.displayName = 'MyClass'
        self.gc._create_education_class = mock.MagicMock(return_value=edu_class_mock)
        self.gc._create_group = mock.MagicMock()

        self.gc.migrate_group_type(udm_fake_group, azure_group, core)

        self.gc._create_education_class.assert_called_once_with(udm_fake_group, core)
        self.gc._create_group.assert_not_called()

    def test_migrate_group_type_from_education_class(self, create_udm_group_object):
        # type: (Callable) -> None
        """migrate_group_type() should call existing_edu.delete() when the
        existing Azure object is an education class and recreate as a normal group."""
        alias = 'o365domain'
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=False)
        # Give it a non-None azure_object_id so the edu-detection branch is entered
        type(udm_fake_group).azure_object_id = mock.PropertyMock(return_value='old-edu-id')

        azure_group = mock.MagicMock()
        azure_group.is_delete = mock.MagicMock(return_value=False)

        new_azure_group = mock.MagicMock()
        self.gc._create_group = mock.MagicMock(return_value=new_azure_group)
        self.gc._create_education_class = mock.MagicMock()

        existing_edu = mock.MagicMock()
        with mock.patch('univention.office365.connector.connector.EducationClassAzure') as mock_edu_cls:
            mock_edu_cls.get.return_value = existing_edu
            result = self.gc.migrate_group_type(udm_fake_group, azure_group, core)

        existing_edu.delete.assert_called_once()
        self.gc._create_group.assert_called_once_with(udm_fake_group, core)
        assert result is new_azure_group

    # ------------------------------------------------------------------
    # Education Class CRUD lifecycle tests (via UDM object modifications)
    # ------------------------------------------------------------------

    def test_crud_create_education_class_full(self, create_udm_group_object):
        # type: (Callable) -> None
        """Full create flow: UDM group with Education Class type triggers
        _create_education_class, which creates via Education Roster API,
        writes Azure ID back to UDM, and adds members."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure, GroupAzure

        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group.get_owners = mock.MagicMock(return_value=[])
        udm_fake_group.modify_azure_attributes = mock.MagicMock()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassCode'] = 'MATH201'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassGrade'] = 'Grade 12'
        test_uuid = 'edu-uuid-1234-5678'
        udm_fake_group.udm_object_reference.oldattr['univentionObjectIdentifier'] = [test_uuid.encode('ASCII')]

        edu_class_mock = mock.MagicMock(spec=EducationClassAzure)
        edu_class_mock.id = 'edu-azure-id'

        group_azure_mock = mock.MagicMock(spec=GroupAzure)
        group_azure_mock.id = 'edu-azure-id'
        group_azure_mock.is_security_group.return_value = False
        group_azure_mock.visibility = None

        self.gc.parse_education_class = mock.MagicMock(return_value=edu_class_mock)
        self.gc.parse = mock.MagicMock(return_value=group_azure_mock)
        self.gc.add_ldap_members_to_azure_group = mock.MagicMock()

        result = self.gc._create_education_class(udm_fake_group, core)

        # Verify education class was created via Education Roster API
        edu_class_mock.create_or_modify.assert_called_once()
        # Verify Azure attributes were written back to UDM with education class flag
        udm_fake_group.modify_azure_attributes.assert_called_once()
        call_args = udm_fake_group.modify_azure_attributes.call_args
        assert call_args[1].get('is_education_class') is True
        assert call_args[1].get('is_security_group') is False
        # Verify members were added
        self.gc.add_ldap_members_to_azure_group.assert_called_once()
        assert isinstance(result, GroupAzure)

    def test_crud_read_education_class_via_parse(self, create_udm_group_object):
        # type: (Callable) -> None
        """parse() returns a minimal GroupAzure stub for education classes,
        while parse_education_class() returns the full EducationClassAzure."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure, GroupAzure

        core = mock.MagicMock()
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365GroupType'] = 'Education Class'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassCode'] = 'CS202'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassGrade'] = 'Grade 10'
        test_uuid = 'read-test-uuid'
        udm_fake_group.udm_object_reference.oldattr['univentionObjectIdentifier'] = [test_uuid.encode('ASCII')]

        # parse() should return a minimal GroupAzure stub
        azure_stub = self.gc.parse(udm_fake_group, core)
        assert isinstance(azure_stub, GroupAzure)
        assert azure_stub.displayName == udm_fake_group.cn
        assert azure_stub.id == udm_fake_group.azure_object_id

        # parse_education_class() should return the full EducationClassAzure
        edu_class = self.gc.parse_education_class(udm_fake_group, core)
        assert isinstance(edu_class, EducationClassAzure)
        assert edu_class.displayName == udm_fake_group.cn
        assert edu_class.classCode == 'CS202'
        assert edu_class.grade == 'Grade 10'
        assert edu_class.externalId == test_uuid

    def test_crud_modify_education_class_attributes(self, create_udm_group_object):
        # type: (Callable) -> None
        """When education class-specific attributes (classCode, grade, description)
        change, check_and_modify_attributes() should detect and apply them."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure

        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias

        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_education_class = mock.MagicMock(return_value=True)

        azure_group = mock.MagicMock()
        azure_group.id = 'edu-azure-id'

        # parse() returns a stub with no group-level differences
        stub = mock.MagicMock()
        stub.get_not_none_values_as_dict.return_value = {}
        self.gc.parse = mock.MagicMock(return_value=stub)
        azure_group.__sub__ = mock.MagicMock(return_value=mock.MagicMock(get_not_none_values_as_dict=mock.MagicMock(return_value={})))

        # Education class from Azure has a different classCode
        existing_edu = mock.MagicMock()
        existing_edu.classCode = 'OLD101'
        new_edu = mock.MagicMock()
        new_edu.classCode = 'NEW101'
        existing_edu.__sub__ = mock.MagicMock(
            return_value=mock.MagicMock(get_not_none_values_as_dict=mock.MagicMock(return_value={'classCode': 'NEW101'}))
        )

        with mock.patch('univention.office365.connector.connector.EducationClassAzure') as mock_edu_cls:
            mock_edu_cls.get.return_value = existing_edu
            self.gc.parse_education_class = mock.MagicMock(return_value=new_edu)

            self.gc.check_and_modify_attributes(udm_fake_group_new, azure_group, core)

            # EducationClassAzure.get should have been called
            mock_edu_cls.get.assert_called_once_with(core, 'edu-azure-id')
            # parse_education_class should have been called
            self.gc.parse_education_class.assert_called_once_with(udm_fake_group_new, core)
            # edu_class.update should have been called with the diff
            existing_edu.update.assert_called_once()

    def test_crud_delete_education_class(self, create_udm_group_object):
        # type: (Callable) -> None
        """Deleting an education class group uses the regular group deactivation
        path (Education-specific delete path is currently commented out)."""
        alias = 'o365domain'
        self.gc._cores[alias] = mock.MagicMock()

        udm_fake_group = create_udm_group_object()
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group.udm_object_reference['UniventionOffice365Data'] = UniventionOffice365Data(
            {'o365domain': {'objectId': 'edu-class-delete-id'}}
        ).to_ldap_str()

        azure_group = mock.MagicMock()
        self.gc.parse = mock.MagicMock(return_value=azure_group)

        self.gc.delete(udm_fake_group)

        # Uses regular group deactivation path
        azure_group.remove_direct_members.assert_called_once()
        azure_group.deactivate.assert_called_once()

    def test_crud_delete_education_class_with_team(self, create_udm_group_object):
        # type: (Callable) -> None
        """When an education class group is also a Team, deleting should first
        archive the Team, then deactivate the group."""
        alias = 'o365domain'
        self.gc._cores[alias] = mock.MagicMock()

        udm_fake_group = create_udm_group_object()
        udm_fake_group.is_team = mock.MagicMock(return_value=True)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group.udm_object_reference['UniventionOffice365Data'] = UniventionOffice365Data(
            {'o365domain': {'objectId': 'edu-team-delete-id'}}
        ).to_ldap_str()

        azure_group = mock.MagicMock()
        self.gc.parse = mock.MagicMock(return_value=azure_group)

        with mock.patch('univention.office365.connector.connector.TeamAzure') as mock_team:
            self.gc.delete(udm_fake_group)
            # Team should be archived first
            mock_team.return_value.deactivate.assert_called_once()
            # Group should be deactivated via regular path
            azure_group.remove_direct_members.assert_called_once()
            azure_group.deactivate.assert_called_once()

    # ------------------------------------------------------------------
    # Team creation from education class group
    # ------------------------------------------------------------------

    def test_create_team_from_education_class_group(self, create_udm_group_object):
        # type: (Callable) -> None
        """When a group is both an education class and a team, create()
        calls _create_education_class() and then convert_group_to_team()."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure, GroupAzure

        alias = 'o365domain'
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=True)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group.get_owners = mock.MagicMock(return_value=[])
        udm_fake_group.modify_azure_attributes = mock.MagicMock()

        # _create_education_class returns a GroupAzure (from self.parse())
        group_azure_mock = mock.MagicMock(spec=GroupAzure)
        group_azure_mock.id = 'edu-team-id'
        group_azure_mock.displayName = 'TeamClass'

        self.gc._create_education_class = mock.MagicMock(return_value=group_azure_mock)
        self.gc.convert_group_to_team = mock.MagicMock()

        self.gc.create(udm_fake_group)

        # _create_education_class is called because is_education_class() is True
        self.gc._create_education_class.assert_called_once_with(udm_fake_group, core)
        # convert_group_to_team should be called with the result
        self.gc.convert_group_to_team.assert_called_once_with(udm_fake_group, group_azure_mock)

    def test_convert_group_to_team_with_education_class(self, create_udm_group_object):
        # type: (Callable) -> None
        """convert_group_to_team() should add owners and create a team
        from the education class backing group. Uses async_task=False
        to exercise the synchronous create_from_group path."""
        alias = 'o365domain'
        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=True)
        udm_fake_group.current_connection_alias = alias
        owners = [mock.MagicMock(dn='owner1'), mock.MagicMock(dn='owner2')]
        udm_fake_group.get_owners = mock.MagicMock(return_value=owners)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)

        azure_group = mock.MagicMock()
        azure_group.id = 'edu-team-backing-group-id'

        self.gc.async_task = False

        with mock.patch('univention.office365.connector.connector.TeamAzure') as mock_team, \
             mock.patch('univention.office365.connector.connector.GroupAzure') as mock_group:
            mock_team.create_from_group = mock.MagicMock()
            mock_group.get = mock.MagicMock(return_value=azure_group)

            self.gc.convert_group_to_team(udm_fake_group, azure_group)

            # Owners should be added
            assert azure_group.add_owner.call_count == len(owners)
            # Team should be created from the backing group
            mock_team.create_from_group.assert_called_once_with(ANY, azure_group.id, education_class=True)

    # ------------------------------------------------------------------
    # Group type migration: Security Group -> Education Class -> Security
    # ------------------------------------------------------------------

    def test_migrate_group_type_security_to_education_class(self, create_udm_group_object):
        # type: (Callable) -> None
        """Migrating from Security Group to Education Class should detect
        the existing object is not an edu class, delete it, and recreate
        via _create_education_class."""
        alias = 'o365domain'
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group.current_connection_alias = alias
        type(udm_fake_group).azure_object_id = mock.PropertyMock(return_value='old-security-group-id')

        azure_group = mock.MagicMock()
        azure_group.id = 'old-security-group-id'
        azure_group.is_delete = mock.MagicMock(return_value=False)

        edu_class = mock.MagicMock()
        edu_class.id = 'new-edu-class-id'
        edu_class.displayName = 'TestClass'

        self.gc._create_education_class = mock.MagicMock(return_value=edu_class)
        self.gc._create_group = mock.MagicMock()

        existing_edu = mock.MagicMock()
        with mock.patch('univention.office365.connector.connector.EducationClassAzure') as mock_edu_cls:
            mock_edu_cls.get.side_effect = MSGraphError(mock.MagicMock(status_code=404), 'Not an edu class')
            result = self.gc.migrate_group_type(udm_fake_group, azure_group, core)

        # Old group should be deleted (via standard path since it's not an edu class)
        azure_group.remove_all_assigned_licenses.assert_called_once()
        azure_group.delete.assert_called_once()
        # New education class should be created
        self.gc._create_education_class.assert_called_once_with(udm_fake_group, core)
        self.gc._create_group.assert_not_called()
        # Result should wrap the education class
        assert result.id == 'new-edu-class-id'

    def test_migrate_group_type_education_class_to_security(self, create_udm_group_object):
        # type: (Callable) -> None
        """Migrating from Education Class to Security Group should detect
        the old education class via EducationClassAzure.get(), delete it,
        and recreate as a regular group."""
        alias = 'o365domain'
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=False)
        type(udm_fake_group).azure_object_id = mock.PropertyMock(return_value='old-edu-id')

        azure_group = mock.MagicMock()
        azure_group.is_delete = mock.MagicMock(return_value=False)

        new_group = mock.MagicMock()
        new_group.id = 'new-security-group-id'
        self.gc._create_group = mock.MagicMock(return_value=new_group)
        self.gc._create_education_class = mock.MagicMock()

        existing_edu = mock.MagicMock()
        with mock.patch('univention.office365.connector.connector.EducationClassAzure') as mock_edu_cls:
            mock_edu_cls.get.return_value = existing_edu
            result = self.gc.migrate_group_type(udm_fake_group, azure_group, core)

        # Old education class should be deleted
        existing_edu.delete.assert_called_once()
        # New security group should be created
        self.gc._create_group.assert_called_once_with(udm_fake_group, core)
        self.gc._create_education_class.assert_not_called()
        assert result is new_group

    def test_migrate_group_type_education_class_to_m365(self, create_udm_group_object):
        # type: (Callable) -> None
        """Migrating from Education Class to M365 Group should detect the old
        education class, delete it, and recreate as an M365 group."""
        alias = 'o365domain'
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=False)
        type(udm_fake_group).azure_object_id = mock.PropertyMock(return_value='old-edu-id')

        azure_group = mock.MagicMock()
        azure_group.is_delete = mock.MagicMock(return_value=False)

        new_group = mock.MagicMock()
        new_group.id = 'new-m365-group-id'
        self.gc._create_group = mock.MagicMock(return_value=new_group)
        self.gc._create_education_class = mock.MagicMock()

        existing_edu = mock.MagicMock()
        with mock.patch('univention.office365.connector.connector.EducationClassAzure') as mock_edu_cls:
            mock_edu_cls.get.return_value = existing_edu
            result = self.gc.migrate_group_type(udm_fake_group, azure_group, core)

        existing_edu.delete.assert_called_once()
        self.gc._create_group.assert_called_once_with(udm_fake_group, core)
        assert result is new_group

    def test_migrate_group_type_education_class_to_team(self, create_udm_group_object):
        # type: (Callable) -> None
        """Migrating from Education Class when the group is also a Team should
        first archive the team, then delete the education class, then recreate."""
        alias = 'o365domain'
        core = mock.MagicMock()
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.is_team = mock.MagicMock(return_value=True)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group.current_connection_alias = alias
        type(udm_fake_group).azure_object_id = mock.PropertyMock(return_value='edu-team-id')

        azure_group = mock.MagicMock()
        azure_group.is_delete = mock.MagicMock(return_value=False)

        edu_class = mock.MagicMock()
        edu_class.id = 'new-edu-team-id'
        edu_class.displayName = 'NewEduTeam'
        self.gc._create_education_class = mock.MagicMock(return_value=edu_class)
        self.gc._create_group = mock.MagicMock()

        existing_edu = mock.MagicMock()
        with mock.patch('univention.office365.connector.connector.TeamAzure') as mock_team, \
             mock.patch('univention.office365.connector.connector.EducationClassAzure') as mock_edu_cls:
            mock_edu_cls.get.return_value = existing_edu
            self.gc.migrate_group_type(udm_fake_group, azure_group, core)
            # Team should be archived first
            mock_team.return_value.deactivate.assert_called_once()
            # Old education class should be deleted
            existing_edu.delete.assert_called_once()

    # ------------------------------------------------------------------
    # check_and_modify_attributes for education classes
    # ------------------------------------------------------------------

    def test_check_and_modify_attributes_education_class(self, create_udm_group_object):
        # type: (Callable) -> None
        """check_and_modify_attributes() should detect education-specific
        attribute changes and call EducationClassAzure.update()."""
        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias

        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_education_class = mock.MagicMock(return_value=True)

        azure_group = mock.MagicMock()
        azure_group.id = 'edu-azure-id'

        # parse() returns a stub with no group-level differences
        stub = mock.MagicMock()
        stub.get_not_none_values_as_dict.return_value = {}
        self.gc.parse = mock.MagicMock(return_value=stub)
        azure_group.__sub__ = mock.MagicMock(return_value=mock.MagicMock(get_not_none_values_as_dict=mock.MagicMock(return_value={})))

        # Education class from Azure has different classCode
        existing_edu = mock.MagicMock()
        existing_edu.classCode = 'OLD101'
        new_edu = mock.MagicMock()
        new_edu.classCode = 'NEW101'
        existing_edu.__sub__ = mock.MagicMock(
            return_value=mock.MagicMock(get_not_none_values_as_dict=mock.MagicMock(return_value={'classCode': 'NEW101'}))
        )

        with mock.patch('univention.office365.connector.connector.EducationClassAzure') as mock_edu_cls:
            mock_edu_cls.get.return_value = existing_edu
            self.gc.parse_education_class = mock.MagicMock(return_value=new_edu)

            self.gc.check_and_modify_attributes(udm_fake_group_new, azure_group, core)

            mock_edu_cls.get.assert_called_once_with(core, 'edu-azure-id')
            self.gc.parse_education_class.assert_called_once_with(udm_fake_group_new, core)
            existing_edu.update.assert_called_once()

    def test_check_and_modify_attributes_education_class_no_change(self, create_udm_group_object):
        # type: (Callable) -> None
        """check_and_modify_attributes() should not call update when there are
        no education-specific attribute changes."""
        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias

        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_education_class = mock.MagicMock(return_value=True)

        azure_group = mock.MagicMock()
        azure_group.id = 'edu-azure-id'

        stub = mock.MagicMock()
        stub.get_not_none_values_as_dict.return_value = {}
        self.gc.parse = mock.MagicMock(return_value=stub)
        azure_group.__sub__ = mock.MagicMock(return_value=mock.MagicMock(get_not_none_values_as_dict=mock.MagicMock(return_value={})))

        existing_edu = mock.MagicMock()
        existing_edu.__sub__ = mock.MagicMock(
            return_value=mock.MagicMock(get_not_none_values_as_dict=mock.MagicMock(return_value={}))
        )
        new_edu = mock.MagicMock()

        with mock.patch('univention.office365.connector.connector.EducationClassAzure') as mock_edu_cls:
            mock_edu_cls.get.return_value = existing_edu
            self.gc.parse_education_class = mock.MagicMock(return_value=new_edu)

            self.gc.check_and_modify_attributes(udm_fake_group_new, azure_group, core)

            existing_edu.update.assert_not_called()

    # ------------------------------------------------------------------
    # Modify flow: education class type change via modify()
    # ------------------------------------------------------------------

    def test_modify_triggers_migrate_on_education_class_type_change(self, create_udm_group_object):
        # type: (Callable) -> None
        """modify() should call migrate_group_type() when the education class
        flag changes between old and new UDM groups."""
        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias
        self.gc._cores[alias] = core

        udm_fake_group_old = create_udm_group_object()
        udm_fake_group_old.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_old.is_team = mock.MagicMock(return_value=False)
        udm_fake_group_old.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group_old.current_connection_alias = alias

        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_team = mock.MagicMock(return_value=False)
        udm_fake_group_new.is_education_class = mock.MagicMock(return_value=False)
        udm_fake_group_new.udm_object_reference.oldattr['description'] = b'new-desc'

        azure_group = mock.MagicMock()
        azure_group.id = 'some-azure-id'
        azure_group.is_delete = mock.MagicMock(return_value=False)

        created_group = mock.MagicMock(name='created_group')
        created_group.id = 'some-azure-id'
        created_group.is_security_group = mock.MagicMock(return_value=False)
        created_group.is_delete = mock.MagicMock(return_value=False)
        self.gc._create_group = mock.MagicMock(return_value=created_group)

        self.gc.migrate_group_type = mock.MagicMock(return_value=azure_group)
        self.gc.check_and_modify_owners = mock.MagicMock()
        self.gc.check_and_modify_teams = mock.MagicMock()
        self.gc.check_and_modify_members = mock.MagicMock()
        self.gc.check_and_modify_attributes = mock.MagicMock()

        with mock.patch('univention.office365.connector.connector.GroupAzure') as mock_group_azure:
            mock_group_azure.get.return_value = created_group
            self.gc.modify(udm_fake_group_old, udm_fake_group_new)

        self.gc.migrate_group_type.assert_called_once_with(udm_fake_group_new, created_group, core)

    def test_modify_education_class_to_team(self, create_udm_group_object):
        # type: (Callable) -> None
        """modify() should call check_and_modify_teams() to create a team
        when a group becomes a team during modification."""
        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias
        self.gc._cores[alias] = core

        udm_fake_group_old = create_udm_group_object()
        udm_fake_group_old.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_old.is_team = mock.MagicMock(return_value=False)
        udm_fake_group_old.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group_old.current_connection_alias = alias

        udm_fake_group_new = create_udm_group_object()
        udm_fake_group_new.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_team = mock.MagicMock(return_value=True)
        udm_fake_group_new.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group_new.udm_object_reference.oldattr['description'] = b'new-desc'

        azure_group = mock.MagicMock()
        azure_group.id = 'edu-team-id'
        azure_group.is_delete = mock.MagicMock(return_value=False)

        created_group = mock.MagicMock(name='created_group')
        created_group.id = 'edu-team-id'
        created_group.is_security_group = mock.MagicMock(return_value=False)
        created_group.is_delete = mock.MagicMock(return_value=False)
        self.gc._create_group = mock.MagicMock(return_value=created_group)

        self.gc.check_and_modify_owners = mock.MagicMock()
        self.gc.check_and_modify_teams = mock.MagicMock()
        self.gc.check_and_modify_members = mock.MagicMock()
        self.gc.check_and_modify_attributes = mock.MagicMock()

        with mock.patch('univention.office365.connector.connector.GroupAzure') as mock_group_azure:
            mock_group_azure.get.return_value = created_group
            self.gc.modify(udm_fake_group_old, udm_fake_group_new)

        self.gc.check_and_modify_teams.assert_called_once_with(
            udm_fake_group_old, udm_fake_group_new, created_group, alias
        )

    # ------------------------------------------------------------------
    # Education class with owners (teachers) and members (students)
    # ------------------------------------------------------------------

    def test_create_education_class_with_teachers_and_students(self, create_udm_group_object):
        # type: (Callable) -> None
        """_create_education_class() should add teachers (owners) and students
        (members) to the education class backing group."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure, GroupAzure

        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias

        udm_fake_group = create_udm_group_object()
        udm_fake_group.current_connection_alias = alias
        owner1 = mock.MagicMock(dn='uid=teacher1,cn=users,dc=test,dc=test')
        owner2 = mock.MagicMock(dn='uid=teacher2,cn=users,dc=test,dc=test')
        udm_fake_group.get_owners = mock.MagicMock(return_value=[owner1, owner2])
        udm_fake_group.modify_azure_attributes = mock.MagicMock()

        edu_class_mock = mock.MagicMock(spec=EducationClassAzure)
        edu_class_mock.id = 'edu-class-with-staff'

        group_azure_mock = mock.MagicMock(spec=GroupAzure)
        group_azure_mock.id = 'edu-class-with-staff'
        group_azure_mock.is_security_group.return_value = False
        group_azure_mock.visibility = None

        self.gc.parse_education_class = mock.MagicMock(return_value=edu_class_mock)
        self.gc.parse = mock.MagicMock(return_value=group_azure_mock)
        self.gc.add_ldap_members_to_azure_group = mock.MagicMock()

        result = self.gc._create_education_class(udm_fake_group, core)

        edu_class_mock.create_or_modify.assert_called_once()
        udm_fake_group.modify_azure_attributes.assert_called_once()
        self.gc.add_ldap_members_to_azure_group.assert_called_once_with(
            udm_fake_group, mock.ANY, core
        )
        assert isinstance(result, GroupAzure)
        assert result.id == 'edu-class-with-staff'

    def test_modify_education_class_grade_change(self, create_udm_group_object):
        # type: (Callable) -> None
        """Modifying the grade attribute of an education class should propagate
        through check_and_modify_attributes."""
        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)

        azure_group = mock.MagicMock()
        azure_group.id = 'edu-grade-test-id'

        stub = mock.MagicMock()
        stub.get_not_none_values_as_dict.return_value = {}
        self.gc.parse = mock.MagicMock(return_value=stub)
        azure_group.__sub__ = mock.MagicMock(return_value=mock.MagicMock(get_not_none_values_as_dict=mock.MagicMock(return_value={})))

        existing_edu = mock.MagicMock()
        existing_edu.grade = 'Grade 5'
        new_edu = mock.MagicMock()
        new_edu.grade = 'Grade 10'
        existing_edu.__sub__ = mock.MagicMock(
            return_value=mock.MagicMock(get_not_none_values_as_dict=mock.MagicMock(return_value={'grade': 'Grade 10'}))
        )

        with mock.patch('univention.office365.connector.connector.EducationClassAzure') as mock_edu_cls:
            mock_edu_cls.get.return_value = existing_edu
            self.gc.parse_education_class = mock.MagicMock(return_value=new_edu)

            self.gc.check_and_modify_attributes(udm_fake_group, azure_group, core)

            existing_edu.update.assert_called_once()

    # ------------------------------------------------------------------
    # Education class creation with fallback on error
    # ------------------------------------------------------------------

    def test_create_education_class_full_flow_with_fallback(self, create_udm_group_object):
        # type: (Callable) -> None
        """Full create flow when education class creation fails should
        fall back to regular M365 group and still add members."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure

        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=False)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group.get_owners = mock.MagicMock(return_value=[])
        udm_fake_group.modify_azure_attributes = mock.MagicMock()

        edu_class_mock = mock.MagicMock(spec=EducationClassAzure)
        edu_class_mock.create_or_modify.side_effect = MSGraphError(mock.MagicMock(status_code=403), 'Education API unavailable')

        fallback_group = mock.MagicMock()
        fallback_group.id = 'fallback-m365-group-id'

        self.gc.parse_education_class = mock.MagicMock(return_value=edu_class_mock)
        self.gc._create_group = mock.MagicMock(return_value=fallback_group)
        self.gc.add_ldap_members_to_azure_group = mock.MagicMock()

        result = self.gc._create_education_class(udm_fake_group, core)

        # Should have attempted education class creation
        edu_class_mock.create_or_modify.assert_called_once()
        # Should have fallen back to M365 group
        self.gc._create_group.assert_called_once_with(udm_fake_group, core)
        # Members are handled inside _create_group (which is mocked here)
        # so add_ldap_members_to_azure_group is not called from _create_education_class
        # UDM attributes should NOT be written for the education class
        udm_fake_group.modify_azure_attributes.assert_not_called()
        assert result is fallback_group

    def test_create_education_class_is_also_team_full_flow(self, create_udm_group_object):
        # type: (Callable) -> None
        """When a group is both an education class and a team, the full create
        flow through _create_group() should: create education class, then the
        remaining group creation, and finally convert_group_to_team is called."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure

        alias = 'o365domain'
        core = mock.MagicMock()
        core.account.alias = alias
        self.gc._cores[alias] = core

        udm_fake_group = create_udm_group_object()
        udm_fake_group.in_azure = mock.MagicMock(return_value=True)
        udm_fake_group.is_team = mock.MagicMock(return_value=True)
        udm_fake_group.is_education_class = mock.MagicMock(return_value=True)
        udm_fake_group.get_owners = mock.MagicMock(return_value=[mock.MagicMock()])
        udm_fake_group.modify_azure_attributes = mock.MagicMock()

        edu_class = mock.MagicMock(spec=EducationClassAzure)
        edu_class.id = 'edu-team-combo-id'
        edu_class.displayName = 'TeamClass'

        # Mock _create_education_class to be called within _create_group
        self.gc.parse_education_class = mock.MagicMock(return_value=edu_class)
        self.gc.add_ldap_members_to_azure_group = mock.MagicMock()
        self.gc.convert_group_to_team = mock.MagicMock()

        self.gc.create(udm_fake_group)

        # create() calls _create_group() which calls _create_education_class()
        # because is_education_class() is True
        self.gc.convert_group_to_team.assert_called()
        # The education class mock should have been passed to convert_group_to_team
        call_args = self.gc.convert_group_to_team.call_args
        assert call_args[0][0] is udm_fake_group

    # ------------------------------------------------------------------
    # Education term attribute getter methods
    # ------------------------------------------------------------------

    def test_get_education_term_display_name(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationTermDisplayName'] = 'Fall 2025'
        assert udm_fake_group.get_education_term_display_name() == 'Fall 2025'

    def test_get_education_term_display_name_none(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        assert udm_fake_group.get_education_term_display_name() is None

    def test_get_education_term_external_id(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationTermExternalId'] = 'term-ext-123'
        assert udm_fake_group.get_education_term_external_id() == 'term-ext-123'

    def test_get_education_term_external_id_none(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        assert udm_fake_group.get_education_term_external_id() is None

    def test_get_education_term_start_date(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationTermStartDate'] = '2025-09-01'
        assert udm_fake_group.get_education_term_start_date() == '2025-09-01'

    def test_get_education_term_start_date_none(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        assert udm_fake_group.get_education_term_start_date() is None

    def test_get_education_term_end_date(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationTermEndDate'] = '2026-01-31'
        assert udm_fake_group.get_education_term_end_date() == '2026-01-31'

    def test_get_education_term_end_date_none(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        assert udm_fake_group.get_education_term_end_date() is None

    def test_get_education_class_code(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassCode'] = 'CS101'
        assert udm_fake_group.get_education_class_code() == 'CS101'

    def test_get_education_class_code_none(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        assert udm_fake_group.get_education_class_code() is None

    def test_get_education_grade(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassGrade'] = 'Grade 10'
        assert udm_fake_group.get_education_grade() == 'Grade 10'

    def test_get_education_grade_none(self, create_udm_group_object):
        # type: (Callable) -> None
        udm_fake_group = create_udm_group_object()
        assert udm_fake_group.get_education_grade() is None

    # ------------------------------------------------------------------
    # parse_education_class with term attributes
    # ------------------------------------------------------------------

    def test_parse_education_class_with_term_attributes(self, create_udm_group_object):
        # type: (Callable) -> None
        """parse_education_class() should populate the term dict when
        term-related attributes are set on the UDM group."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure

        core = mock.MagicMock()
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassCode'] = 'MATH301'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassGrade'] = 'Grade 12'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationTermDisplayName'] = 'Spring 2026'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationTermExternalId'] = 'term-spring-2026'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationTermStartDate'] = '2026-02-01'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationTermEndDate'] = '2026-06-30'
        test_uuid = 'term-test-uuid'
        udm_fake_group.udm_object_reference.oldattr['univentionObjectIdentifier'] = [test_uuid.encode('ASCII')]

        edu_class = self.gc.parse_education_class(udm_fake_group, core)

        assert isinstance(edu_class, EducationClassAzure)
        assert edu_class.term is not None
        assert edu_class.term['displayName'] == 'Spring 2026'
        assert edu_class.term['externalId'] == 'term-spring-2026'
        assert edu_class.term['startDate'] == '2026-02-01'
        assert edu_class.term['endDate'] == '2026-06-30'

    def test_parse_education_class_without_term_attributes(self, create_udm_group_object):
        # type: (Callable) -> None
        """parse_education_class() should set term to None when no
        term-related attributes are set on the UDM group."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure

        core = mock.MagicMock()
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassCode'] = 'CS101'
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationClassGrade'] = 'Grade 5'
        test_uuid = 'no-term-uuid'
        udm_fake_group.udm_object_reference.oldattr['univentionObjectIdentifier'] = [test_uuid.encode('ASCII')]

        edu_class = self.gc.parse_education_class(udm_fake_group, core)

        assert isinstance(edu_class, EducationClassAzure)
        assert edu_class.term is None

    def test_parse_education_class_with_partial_term_attributes(self, create_udm_group_object):
        # type: (Callable) -> None
        """parse_education_class() should only include the term dict keys
        for attributes that are actually set."""
        from univention.office365.microsoft.objects.azureobjects import EducationClassAzure

        core = mock.MagicMock()
        udm_fake_group = create_udm_group_object()
        udm_fake_group.udm_object_reference['UniventionMicrosoft365EducationTermStartDate'] = '2026-01-15'
        test_uuid = 'partial-term-uuid'
        udm_fake_group.udm_object_reference.oldattr['univentionObjectIdentifier'] = [test_uuid.encode('ASCII')]

        edu_class = self.gc.parse_education_class(udm_fake_group, core)

        assert isinstance(edu_class, EducationClassAzure)
        assert edu_class.term is not None
        assert edu_class.term == {'startDate': '2026-01-15'}
        assert 'displayName' not in edu_class.term
        assert 'externalId' not in edu_class.term
        assert 'endDate' not in edu_class.term

    # ------------------------------------------------------------------
    # GroupConnector.attrs includes term attributes
    # ------------------------------------------------------------------

    def test_group_connector_attrs_includes_term_attributes(self):
        # type: () -> None
        """GroupConnector.attrs must include the term-related LDAP
        attributes so that changes to them trigger a sync."""
        gc = GroupConnector({'o365domain': 'initialized'})
        assert 'univentionMicrosoft365EducationTermDisplayName' in gc.attrs
        assert 'univentionMicrosoft365EducationTermExternalId' in gc.attrs
        assert 'univentionMicrosoft365EducationTermStartDate' in gc.attrs
        assert 'univentionMicrosoft365EducationTermEndDate' in gc.attrs

    def test_group_connector_attrs_includes_class_attributes(self):
        # type: () -> None
        """GroupConnector.attrs must include classCode and grade attributes."""
        gc = GroupConnector({'o365domain': 'initialized'})
        assert 'univentionMicrosoft365EducationClassCode' in gc.attrs
        assert 'univentionMicrosoft365EducationClassGrade' in gc.attrs


