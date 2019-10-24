# -*- coding: utf-8 -*-
#
# Univention Office 365 - UDM hook to set user property
# UniventionOffice365userPrincipalName that is configured notEditable=1
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

import json
import base64
import zlib

import univention.debug as ud
from univention.admin.hook import simpleHook
import univention.admin.uexceptions
from univention.lib.i18n import Translation

_ = Translation('univention-admin-handlers-office365').translate
msg_require_mail = _("Office 365 users must have a primary e-mail address specified.")


class OfficeUserPrincipalNameHook(simpleHook):
	type = "OfficeUserPrincipalNameHook"

	@staticmethod
	def log(msg):
		ud.debug(ud.LISTENER, ud.ERROR, msg)

	@staticmethod
	def str2bool(val):
		try:
			return bool(int(val))
		except TypeError:
			# None
			return False

	@staticmethod
	def get_user_principal_name(azure_data_encoded):
		adata = json.loads(zlib.decompress(base64.decodestring(azure_data_encoded)))
		try:
			return adata.get("userPrincipalName")
		except AttributeError:
			# None
			# (We should actually never get here, as long as UniventionOffice365Enabled=1.)
			return ""

	def hook_ldap_modlist(self, module, ml=[]):
		if module.hasChanged("UniventionOffice365Data"):
			old = module.get("UniventionOffice365userPrincipalName")
			if module.get("UniventionOffice365Enabled"):
				new = self.get_user_principal_name(module["UniventionOffice365Data"])
			else:
				new = ""
			if old != new:
				ml.append(("UniventionOffice365userPrincipalName", old, new))
		return ml

	def hook_ldap_pre_create(self, module):
		if self.str2bool(module.get("UniventionOffice365Enabled")) and not module.get("mailPrimaryAddress"):
			raise univention.admin.uexceptions.valueError(msg_require_mail)

	def hook_ldap_pre_modify(self, module):
		if self.str2bool(module.get("UniventionOffice365Enabled")) and not module.get("mailPrimaryAddress"):
			raise univention.admin.uexceptions.valueError(msg_require_mail)
