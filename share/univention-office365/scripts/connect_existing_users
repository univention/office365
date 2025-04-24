#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Univention Office 365 - print users and groups
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
"""
A script to connect existing UCS users to existing Azure AD users
requires a working AD connection setup by the O365 umc wizard
requires at least the UCS uid and Azure AD UPN
If the UCS account has no mailPrimaryAddress, --set-mail can be used
"""

from __future__ import print_function

from argparse import ArgumentParser
import base64
import sys

import univention.admin.uldap
import univention.admin.modules
from ldap.filter import filter_format
from univention.config_registry import ConfigRegistry

from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError
from univention.office365.microsoft.account import AzureAccount
from univention.office365.udmwrapper.udmobjects import UniventionOffice365Data


class UserArgs:
	"""
	Data container representing all arguments to connect one user
	uid and upn are required, the rest is optional
	"""
	def __init__(self, uid, upn, adconnection="defaultADconnection", set_mail=False, maildomain="", mail_localpart_from_uid=False, mail_localpart_from_upn=False, activate=False, modify=False):
		self.uid = uid
		self.upn = upn
		self.adconnection = adconnection
		self.set_mail = set_mail
		self.maildomain = maildomain
		self.mail_localpart_from_uid = mail_localpart_from_uid
		self.mail_localpart_from_upn = mail_localpart_from_upn
		self.activate = activate
		self.modify = modify


def parse_arguments(args):
	"""
	parses CLI arguments and typecasts them to a UserArgs instance
	"""
	parser = ArgumentParser()
	parser.add_argument('-m', '--modify', action='store_true', help='Modify users, default: dry-run')

	parser.add_argument('-a', '--activate', action='store_true', help='Also activate the user for Office365, the listener then immediately syncs the object')
	parser.add_argument('-p', '--upn', required=True, help='The Azure username (UPN, userPrincipleName)')
	parser.add_argument('-u', '--uid', required=True, help='The LDAP username (uid)')
	parser.add_argument('-c', '--adconnection', default='defaultADconnection', help='The initialized AD connection the user is activated for, default: %(default)s')
	parser.add_argument('--set_mail', action='store_true', help='Also set the mailPrimaryAddress at the user')
	parser.add_argument('--maildomain', help='set the given maildomain at the user object. Has to be configured in udm mail/domain.')

	parser.add_argument('--mail_localpart_from_uid', action='store_true', help='set the mailPrimaryAddress localpart to the user uid.')
	parser.add_argument('--mail_localpart_from_upn', action='store_true', help='set the mailPrimaryAddress localpart to the UPN localpart (prevents renaming the Azure account localpart).')

	args = parser.parse_args(args)

	# validate mail args
	if args.set_mail:
		if args.mail_localpart_from_uid and args.mail_localpart_from_upn:
			parser.error("Only one of --mail_localpart_from_uid and --mail_localpart_from_upn may be selected")
		if not args.mail_localpart_from_uid and not args.mail_localpart_from_upn:
			parser.error("One of --mail_localpart_from_uid and --mail_localpart_from_upn has to be selected")
		if not args.maildomain:
			parser.error("--maildomain has to be given")

	user_args = UserArgs(**vars(args))

	return user_args


class ExistingUserConnector:
	"""connect existing UCS users with existing Azure AD users"""
	def __init__(self):
		"""Initialize UDM connection"""
		ucr = ConfigRegistry()
		ucr.load()
		self.base = ucr["ldap/base"]
		self.lo, po = univention.admin.uldap.getAdminConnection()
		univention.admin.modules.update()
		self.usermod = univention.admin.modules.get('users/user')
		univention.admin.modules.init(self.lo, po, self.usermod)

	def get_azure_user_id(self, adconnection, user_principal_name):
		# Initialize Azure connection
		azure_account = AzureAccount(adconnection)
		if not azure_account.is_initialized():
			print("connection %s not initialized" % (adconnection,))
			exit(5)
		core = MSGraphApiCore(azure_account)

		try:
			azure_user_id = core.get_user(user_principal_name, selection="id")['id']
			return core, azure_user_id
		except MSGraphError as err:
			print("Error while querying Azure user:", err)
			exit(2)

	def get_udm_user_and_entryuuid(self, uid):
		udm_user = []
		udm_user = self.usermod.lookup(None, self.lo, filter_s=filter_format("uid=%s", (uid, )), base=self.base)
		if len(udm_user) != 1:
			print("Could not find user with uid=%s in UDM/LDAP" % (uid,))
			exit(1)

		user = udm_user[0]
		user.open()

		try:
			entryuuid = user.entryuuid
		except AttributeError:  # <= UCS 5.0-2
			entryuuid = self.lo.get(user.dn, attr=["entryUUID"])["entryUUID"][0].decode("UTF-8")

		return user, entryuuid

	def modify_udm_user(self, udm_user, azure_user_id, user_args):
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
		udm_user['UniventionOffice365ADConnectionAlias'].append(user_args.adconnection)

		if user_args.set_mail:
			localpart = user_args.uid if user_args.mail_localpart_from_uid else user_args.upn.rsplit("@", 1)[0]

			udm_user["mailPrimaryAddress"] = "%s@%s" % (localpart, user_args.maildomain)
		if user_args.activate:
			udm_user["UniventionOffice365Enabled"] = "1"

		udm_user.modify()

	def connect_user(self, user_args):
		core, azure_user_id = self.get_azure_user_id(user_args.adconnection, user_args.upn)
		udm_user, entryuuid = self.get_udm_user_and_entryuuid(user_args.uid)

		if not user_args.modify:
			print("Would update LDAP user %s; objectid=%s, and azure user entryuuid is %s" % (user_args.uid, azure_user_id, entryuuid))
			exit(0)

		try:
			self.modify_udm_user(udm_user, azure_user_id, user_args)
			# Modify AzureUser

			core.modify_user(azure_user_id, {'onPremisesImmutableId': base64.b64encode(entryuuid.encode('ASCII')).decode('ASCII')})

			print("Modified: LDAP user %s; azure objectid=%s; ucs mail=%s, and ldap entryuuid is %s" % (user_args.uid, azure_user_id, udm_user["mailPrimaryAddress"], entryuuid))
		except MSGraphError as exc:
			print("Error while connecting users:", exc)
			exit(4)


if __name__ == '__main__':
	user_args = parse_arguments(sys.argv[1:])

	connector = ExistingUserConnector()
	connector.connect_user(user_args)
