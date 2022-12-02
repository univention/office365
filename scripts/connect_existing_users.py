#!/usr/bin/env python2.7
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

from univention.config_registry import ConfigRegistry
from univention.office365.azure_handler import AzureHandler
from univention.office365.azure_auth import AzureAuth
from univention.office365.listener import Office365Listener
import univention.admin.uldap
import univention.admin.objects
from optparse import OptionParser
import traceback
import base64


# A script to connect existing UCS users to existing Azure AD users
# requires a working AD connection setup by the O365 umc wizard
# requires at least the UCS uid and Azure AD UPN
# If the UCS account has no mailPrimaryAddress, --set-mail can be used
if __name__ == '__main__':
	parser = OptionParser()
	parser.add_option('-m', '--modify', dest='modify', action='store_true', help='Modify users, default: dry-run')
	parser.add_option('-p', '--upn', dest='upn', help='The Azure username (UPN, userPrincipleName)')
	parser.add_option('-u', '--uid', dest='uid', help='The LDAP username (uid)')
	parser.add_option('-c', '--adconnection', dest='adconnection', default='defaultADconnection', help='The initialized AD connection the user is activated for, default: defaultADconnection')
	parser.add_option('--set_mail', action='store_true', dest='set_mail', help='Also set the mailPrimaryAddress at the user')
	parser.add_option('--maildomain', dest='maildomain', help='set the given maildomain at the user object. Has to be configured in udm mail/domain.')
	parser.add_option('--mail_localpart_from_uid', dest='m_from_uid', action='store_true', help='set the mailPrimaryAddress localpart to the user uid.')
	parser.add_option('--mail_localpart_from_upn', dest='m_from_upn', action='store_true', help='set the mailPrimaryAddress localpart to the UPN localpart (prevents renaming the Azure account localpart).')
	parser.add_option('-a', '--activate', dest='activate', action='store_true', help='Also activate the user for Office365, the listener then immediataly syncs the object')
	options, args = parser.parse_args()

	if not options.upn:
		parser.error("Azure username (UPN) not given")
	if not options.uid:
		parser.error("LDAP username (uid) not given")

	if options.set_mail:
		if options.m_from_uid and options.m_from_upn:
			parser.error("Only one of --mail_localpart_from_uid and --mail_localpart_from_upn may be selected")
		if not options.m_from_uid and not options.m_from_upn:
			parser.error("One of --mail_localpart_from_uid and --mail_localpart_from_upn has to be selected")
		if not options.maildomain:
			parser.error("--maildomain has to be given")

	# test if ad connection is initialized at all
	if not AzureAuth.is_initialized(options.adconnection):
		print("connection %s not initialized" % options.adconnection)
		exit(5)

	ucr = ConfigRegistry()
	ucr.load()
	base = ucr["ldap/base"]
	ah = AzureHandler(ucr, "connectusers", options.adconnection)
	lo, po = univention.admin.uldap.getAdminConnection()
	univention.admin.modules.update()
	usermod = univention.admin.modules.get('users/user')
	univention.admin.modules.init(lo, po, usermod)
	config = univention.admin.config.config()

	lookup_result = []
	lookup_result = usermod.lookup(config, lo, filter_s="uid=%s" % options.uid, base=base)

	if len(lookup_result) != 1:
		print "Could not find user with uid=%s" % options.uid
		exit(1)

	# UDM does not read the entryUUID, so get it separately...
	ldap_entryuuid = lo.search(filter="uid=%s" % options.uid, base=base, attr=["entryUUID"])[0][1]["entryUUID"][0]

	azure_lookup_result = []
	try:
		azure_lookup_result = ah.list_users(ofilter="userPrincipalName eq '%s'" % options.upn)
	except Exception as ex:
		print "Error while querying Azure user"
		traceback.print_exc()
		exit(2)

	if len(azure_lookup_result["value"]) != 1:
		print "Could not find azure with upn=%s, result was: %s" % (options.upn, azure_lookup_result)
		exit(3)

	azure_objectid = azure_lookup_result["value"][0]["objectId"]

	if options.modify:
		try:
			user = lookup_result[0]
			user.open()

			azure_data_decoded = {}
			if user['UniventionOffice365Data']:
				azure_data_decoded = Office365Listener.decode_o365data(user['UniventionOffice365Data'])

			aliases = user['UniventionOffice365ADConnectionAlias'] or []
			aliases.append(options.adconnection)
			user['UniventionOffice365ADConnectionAlias'] = aliases

			azure_data_decoded[options.adconnection] = {
					'userPrincipalName': options.upn,
					'objectId': azure_objectid,
				}
			user["UniventionOffice365Data"] = Office365Listener.encode_o365data(azure_data_decoded)
			user.modify()

			ah.modify_user(azure_objectid, {"immutableId": base64.encodestring(ldap_entryuuid).rstrip()})
			if options.set_mail:
				localpart = ""
				if options.m_from_uid:
					localpart = options.uid
				if options.m_from_upn:
					localpart = options.upn.split("@")[0]
				user["mailPrimaryAddress"] = "%s@%s" % (localpart, options.maildomain)
			if options.activate:
				user["UniventionOffice365Enabled"] = "1"

			user.modify()

			print "Modified: LDAP user %s; azure objectid=%s; ucs mail=%s, and ldap entryuuid is %s" % (options.uid, azure_objectid, user["mailPrimaryAddress"], ldap_entryuuid)
		except Exception as ex:
			print "Error while connecting users"
			traceback.print_exc()
			exit(4)
	else:
		print "Would update LDAP user %s; objectid=%s, and azure user entryuuid is %s" % (options.uid, azure_objectid, ldap_entryuuid)
