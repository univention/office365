#!/usr/share/ucs-test/runner pytest-3 -s -l -vv
## -*- coding: utf-8 -*-
## desc: connect existing users
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365

import base64
import pytest
import subprocess

from helpers.office365_test_helpers import udm_user_args
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.objects.azureobjects import UserAzure
from univention.office365.ucr_helper import UCRHelper
from univention.office365.udm_helper import UDMHelper

alias = 'azuretestdomain'


@pytest.fixture
def azure_user(random_username):
    core = MSGraphApiCore(AzureAccount(alias))

    user_name = random_username()
    mailNickname = user_name
    mail_primary_address = f'{mailNickname}@alphadistrict.onmicrosoft.com'
    azure_user_data = {
        'displayName': user_name,
        'userPrincipalName': mail_primary_address,
        'surname': user_name,
        'passwordProfile': {
            'password': 'Soqa928724',
            'forceChangePasswordNextSignInWithMfa': False,
        },
        'mailNickname': mailNickname,
        'accountEnabled': True,
        'usageLocation': UCRHelper.get_usage_location(),
    }
    user_azure = UserAzure(**azure_user_data)
    user_azure.set_core(core)
    print(f'*** Creating user in Azure... {user_azure.id} ***')
    user_azure.create()
    yield user_azure
    user_azure.delete()


def test_connect_existing_users(udm, ucr, azure_user):
    udm_helper = UDMHelper(None)

    core = azure_user._core
    mail_primary_address = azure_user.userPrincipalName
    user_args = udm_user_args(ucr, minimal=False)

    user_dn, ucs_username = udm.create_user(check_for_drs_replication=True, **user_args)
    print(f'*** Creating user with all possible properties... {user_dn} ***')

    script = '/usr/share/univention-office365/scripts/connect_existing_users'
    command = f'{script} -u {ucs_username} -p {mail_primary_address} -c {alias} -m'
    print(f'Running command: {command}')
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    assert result.returncode == 0, f'Command failed with error: {result.stderr}'
    assert 'Modified: LDAP user ' in result.stdout, 'Command output does not contain expected message.'
    assert azure_user.id in result.stdout, 'Command output does not contain expected user ID.'

    udm_user_after = udm_helper.get_udm_user(user_dn)
    user_azure_after = UserAzure.get(core, azure_user.id, selection=['id', 'onPremisesImmutableId'])

    assert base64.b64decode(user_azure_after.onPremisesImmutableId) == udm_user_after.oldattr['entryUUID'][0], 'User ID in Azure does not match the one in UDM.'
    assert alias in udm_user_after.info['UniventionOffice365ADConnectionAlias'], 'AD connection alias in UDM does not match the expected value.'
    assert (alias, mail_primary_address) in udm_user_after.info['UniventionOffice365ADConnections']
