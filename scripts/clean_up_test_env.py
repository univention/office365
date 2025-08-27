#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Univention Office 365 - print users subscriptions
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only


import sys
from operator import itemgetter

from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.objects.azureobjects import UserAzure, GroupAzure, SubscriptionAzure
from univention.office365.ucr_helper import UCRHelper

user_ignorelist = [
    'admin@alphadistrict.onmicrosoft.com',
    'webmaster_univention-azure-tests.de#EXT#@alphadistrict.onmicrosoft.com',
    'dtroeder@univentiontestgmbh.onmicrosoft.com',
    'edamrose@univentiontestgmbh.onmicrosoft.com',
    'azureadmin1@univentiontestgmbh.onmicrosoft.com',
]
group_ignorelist = ['']


def clean_up_test_env(adconnection_alias):
    core = MSGraphApiCore(AzureAccount(adconnection_alias))

    users = UserAzure.list(core)
    groups = GroupAzure.list(core)
    for user in users:
        print(user.userPrincipalName)
        if user.userPrincipalName not in user_ignorelist:
            print('Deleting user {!r}'.format(user.userPrincipalName))
            core.delete_user(user.id)
    for group in groups:
        print(group.displayName)
        if group.displayName not in group_ignorelist:
            print('Deleting group {!r}'.format(group.displayName))
            core.delete_group(group.id)


if __name__ == '__main__':
    if not len(sys.argv) == 2:
        print('Usage: {} [Azure AD connection alias]'.format(sys.argv[0]))
        print('Available Azure AD connection aliases: {}'.format(', '.join(UCRHelper.get_adconnection_aliases().keys())))
        sys.exit(1)
    try:
        adconnection_alias = sys.argv[1]
        adconnection_aliases = UCRHelper.get_adconnection_aliases().keys()
        initialized_adconnections = [ta for ta in adconnection_aliases if AzureAccount(ta).is_initialized()]
        if adconnection_alias not in adconnection_aliases:
            print('Usage: {} [Azure AD connection alias]'.format(sys.argv[0]))
            print('Unknown Azure AD connection alias {!r}.'.format(adconnection_alias))
            print('Available Azure AD connection aliases: {}'.format(', '.join(adconnection_aliases)))
            sys.exit(1)
        elif adconnection_alias not in initialized_adconnections:
            print('Usage: {} [Azure AD connection alias]'.format(sys.argv[0]))
            print('Azure AD connection not yet initialized: {!r}.'.format(adconnection_alias))
            sys.exit(1)
        print('Using Azure AD connection alias {!r}.'.format(adconnection_alias))
    except IndexError:
        adconnection_alias = None

    clean_up_test_env(adconnection_alias)
