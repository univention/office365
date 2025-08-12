#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Univention Office 365 - print users subscriptions
#
# Copyright 2016-2022 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.


import sys
from operator import itemgetter

from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.objects.azureobjects import UserAzure, GroupAzure, SubscriptionAzure
from univention.office365.ucr_helper import UCRHelper

user_ignorelist = [
	"admin@alphadistrict.onmicrosoft.com",
	"webmaster_univention-azure-tests.de#EXT#@alphadistrict.onmicrosoft.com",
	"dtroeder@univentiontestgmbh.onmicrosoft.com",
	"edamrose@univentiontestgmbh.onmicrosoft.com",
	"azureadmin1@univentiontestgmbh.onmicrosoft.com",
]
group_ignorelist = [
	""
]


def clean_up_test_env(adconnection_alias):
	core = MSGraphApiCore(AzureAccount(adconnection_alias))

	users = UserAzure.list(core)
	groups = GroupAzure.list(core)
	for user in users:
		print(user.userPrincipalName)
		if user.userPrincipalName not in user_ignorelist:
			print("Deleting user {!r}".format(user.userPrincipalName))
			core.delete_user(user.id)
	for group in groups:
		print(group.displayName)
		if group.displayName not in group_ignorelist:
			print("Deleting group {!r}".format(group.displayName))
			core.delete_group(group.id)


if __name__ == '__main__':
	if not len(sys.argv) == 2:
		print('Usage: {} [Azure AD connection alias]'.format(sys.argv[0]))
		print('Available Azure AD connection aliases: {}'.format(", ".join(UCRHelper.get_adconnection_aliases().keys())))
		sys.exit(1)
	try:
		adconnection_alias = sys.argv[1]
		adconnection_aliases = UCRHelper.get_adconnection_aliases().keys()
		initialized_adconnections = [ta for ta in adconnection_aliases if AzureAccount(ta).is_initialized()]
		if adconnection_alias not in adconnection_aliases:
			print('Usage: {} [Azure AD connection alias]'.format(sys.argv[0]))
			print('Unknown Azure AD connection alias {!r}.'.format(adconnection_alias))
			print('Available Azure AD connection aliases: {}'.format(", ".join(adconnection_aliases)))
			sys.exit(1)
		elif adconnection_alias not in initialized_adconnections:
			print('Usage: {} [Azure AD connection alias]'.format(sys.argv[0]))
			print('Azure AD connection not yet initialized: {!r}.'.format(adconnection_alias))
			sys.exit(1)
		print('Using Azure AD connection alias {!r}.'.format(adconnection_alias))
	except IndexError:
		adconnection_alias = None

	clean_up_test_env(adconnection_alias)
