#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Univention Office 365 - print users and groups
#
# Copyright 2016-2019 Univention GmbH
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

from __future__ import print_function
from argparse import ArgumentParser
import base64
import sys

from univention.config_registry import ConfigRegistry
import univention.admin.uldap

from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError
from univention.office365.microsoft.account import AzureAccount
from univention.office365.udmwrapper.udmobjects import UniventionOffice365Data


# A script to connect existing UCS users to existing Azure AD users
# requires a working AD connection setup by the O365 umc wizard
# requires at least the UCS uid and Azure AD UPN
# If the UCS account has no mailPrimaryAddress, --set-mail can be used


def parse_arguments(args):
	"""
	parses cli arguments and typecasts them to a UserArgs instance
	"""
	parser = ArgumentParser()
	parser.add_argument('-m', '--modify', action='store_true', help='Modify users, default: dry-run')
	parser.add_argument('-a', '--activate', dest='activate', action='store_true', help='Also activate the user for Office365, the listener then immediataly syncs the object')
	parser.add_argument('-p', '--upn', required=True, help='The Azure username (UPN, userPrincipleName)')
	parser.add_argument('-u', '--uid', required=True, help='The LDAP username (uid)')
	parser.add_argument('-c', '--adconnection', default='defaultADconnection', help='The initialized AD connection the user is activated for, default: %(default)s')
	parser.add_argument('--set_mail', action='store_true', help='Also set the mailPrimaryAddress at the user')
	parser.add_argument('--maildomain', help='set the given maildomain at the user object. Has to be configured in udm mail/domain.')

	parser.add_argument('--mail_localpart_from_uid', dest='mail_localpart_from_uid', action='store_true', help='set the mailPrimaryAddress localpart to the user uid.')
	parser.add_argument('--mail_localpart_from_upn', dest='mail_localpart_from_upn', action='store_true', help='set the mailPrimaryAddress localpart to the UPN localpart (prevents renaming the Azure account localpart).')

	args = parser.parse_args(args)

	# validate mail args
	if args.set_mail:
		if args.mail_localpart_from_uid and args.mail_localpart_from_upn:
			parser.error("Only one of --mail_localpart_from_uid and --mail_localpart_from_upn may be selected")
		if not args.mail_localpart_from_uid and not args.mail_localpart_from_upn:
			parser.error("One of --mail_localpart_from_uid and --mail_localpart_from_upn has to be selected")
		if not args.maildomain:
			parser.error("--maildomain has to be given")

	user_args = args
	return user_args


def get_udm_user_and_entryUUID(uid):
	"""
	UDM does not read the entryUUID, so get it separately
	returns udm_user, raw_entryuuid
	"""
	# Initialize UDM connection
	ucr = ConfigRegistry()
	ucr.load()
	base = ucr["ldap/base"]
	lo, po = univention.admin.uldap.getAdminConnection()
	univention.admin.modules.update()
	usermod = univention.admin.modules.get('users/user')
	univention.admin.modules.init(lo, po, usermod)
	config = univention.admin.config.config()

	udm_user = []
	udm_user = usermod.lookup(config, lo, filter_s="uid=%s" % uid, base=base)
	if len(udm_user) != 1:
		print("Could not find user with uid=%s in UDM/LDAP" % uid)
		exit(1)

	raw_entryuuid = lo.search(
		filter="uid=%s" % uid, base=base, attr=["entryUUID"]
	)[0][1]["entryUUID"][0]

	if not isinstance(raw_entryuuid, bytes):
		raw_entryuuid = raw_entryuuid.encode("ASCII")

	return udm_user, raw_entryuuid


def get_azure_user_id(self, adconnection, user_principal_name):
	# Initialize Azure connection
	azure_account = AzureAccount(adconnection)
	if not azure_account.is_initialized():
		print("connection %s not initialized" % adconnection)
		exit(5)
	core = MSGraphApiCore(azure_account)

	try:
		azure_user_id = core.get_user(user_principal_name, selection="id")['id']
	except MSGraphError as err:
		print("Error while querying Azure user")
		print(err)
		exit(2)

		return core, azure_user_id


def modify_udm_user(self, udm_user, azure_user_id, user_args):
	# Open UDM user
	udm_user = udm_user[0]
	udm_user.open()

	# Create AzureData
	if udm_user.get('UniventionOffice365Data'):
		azure_data = UniventionOffice365Data.from_ldap(udm_user['UniventionOffice365Data'])
	else:
		azure_data = UniventionOffice365Data({})

	azure_data[user_args.adconnection] = {
		'userPrincipalName': user_args.upn,
		'objectId': azure_user_id
	}

	# Modify UDMUser
	udm_user["UniventionOffice365Data"] = azure_data.to_ldap_str()

	# add aliases to UDM User
	aliases = udm_user.get(
		'UniventionOffice365ADConnectionAlias', []
	).append(user_args.adconnection)
	udm_user['UniventionOffice365ADConnectionAlias'] = aliases

	if user_args.set_mail:
		localpart = user_args.uid if user_args.mail_localpart_from_uid else user_args.upn.split("@")[0]

		udm_user["mailPrimaryAddress"] = "%s@%s" % (localpart, user_args.maildomain)
	if user_args.activate:
		udm_user["UniventionOffice365Enabled"] = "1"

	udm_user.modify()


def connect_user(self, user_args):
	core, azure_user_id = self.get_azure_user_id(user_args.adconnection, user_args.upn)
	udm_user, raw_entryuuid = self.get_udm_user_and_entryUUID(user_args.uid)

	if not user_args.modify:
		print("Would update LDAP user %s; objectid=%s, and azure user entryuuid is %s" % (user_args.uid, azure_user_id, raw_entryuuid))
		exit(0)

	try:
		self.modify_udm_user(udm_user, azure_user_id, user_args)
		# Modify AzureUser

		core.modify_user(azure_user_id, {'onPremisesImmutableId': base64.b64encode(raw_entryuuid).decode('UTF-8')})

		print("Modified: LDAP user %s; azure objectid=%s; ucs mail=%s, and ldap entryuuid is %s" % (user_args.uid, azure_user_id, udm_user["mailPrimaryAddress"], raw_entryuuid))
	except MSGraphError as ex:
		print("Error while connecting users")
		print(ex)
		exit(4)


if __name__ == '__main__':
	user_args = parse_arguments(sys.argv[1:])
	connect_user(user_args)
