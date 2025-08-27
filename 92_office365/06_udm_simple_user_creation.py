#!/usr/share/ucs-test/runner pytest-3 -s -l -vv
## -*- coding: utf-8 -*-
## desc: create user UDM, replicate in azure, check data attribute
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365

import pytest

from helpers.office365_test_helpers import udm_user_args, check_user_id_from_azure, o365_connection, azuretestdomain
from helpers.retry import retry_call


class Test_UDMUserCreation2:
    @pytest.mark.parametrize('test_duplicate_mail', [False, True])
    @pytest.mark.parametrize('adconnection_alias, adconnection_srcpath', [o365_connection, azuretestdomain], indirect=True)
    def test_udm_simple_user_creation(self, udm, ucr, restart_listener_after_test, adconnection, adconnection_alias, test_duplicate_mail):
        """
        This test is used to create user UDM, replicate in azure, check data attribute.
        The next operations are performed on the two preconfigured connections to Azure:
        - create UDM user
        - wait for the user to be replicated in Azure
        - retrieve the user from Azure and check the id
        """

        user_args = udm_user_args(ucr, minimal=False)
        user_args['set']['UniventionOffice365Enabled'] = 1
        user_args['set']['UniventionOffice365ADConnectionAlias'] = adconnection_alias

        # test for handling of duplicate mail addresses by saving a upper case copy of mailPrimaryAddress into e-mail
        if test_duplicate_mail:
            user_args['append']['e-mail'].append(user_args['set']['mailPrimaryAddress'].upper())

        print('*** Creating user with all possible properties...')
        user_dn, username = udm.create_user(check_for_drs_replication=True, **user_args)

        fail_msg = 'User was not created properly (no UniventionOffice365ObjectID).'
        user_id = retry_call(check_user_id_from_azure, fargs=[adconnection_alias, user_dn, fail_msg], tries=5, delay=2)
