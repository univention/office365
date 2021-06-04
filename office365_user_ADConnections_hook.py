# -*- coding: utf-8 -*-
#
# Univention Microsoft 365 - UDM hook to access ADConnection data
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

from univention.admin.hook import simpleHook
import univention.admin.uexceptions
from univention.lib.i18n import Translation
from univention.office365.listener import Office365Listener
import zlib

_ = Translation('univention-admin-handlers-office365').translate
msg_require_mail = _("Microsoft 365 users must have a primary e-mail address specified.")
msg_require_owner = _("In order to create a Microsoft 365 team from a group, at least one group/team owner has to be specified.")


def str2bool(val):
	try:
		return bool(int(val))
	except TypeError:
		# None
		return False


class Microsoft365GroupHook(simpleHook):
	type = "Microsoft365GroupHook"

	def hook_ldap_pre_create(self, module):
		if str2bool(module.get("UniventionMicrosoft365Team")) and not module.get("UniventionMicrosoft365GroupOwners"):
			raise univention.admin.uexceptions.valueError(msg_require_owner)

	def hook_ldap_pre_modify(self, module):
		if str2bool(module.get("UniventionMicrosoft365Team")) and not module.get("UniventionMicrosoft365GroupOwners"):
			raise univention.admin.uexceptions.valueError(msg_require_owner)


class Office365ADConnectionsHook(simpleHook):
	type = "Office365ADConnectionsHook"

	def hook_open(self, module):
		object_id = module.get("UniventionOffice365ObjectID")
		if object_id:
			# represent unmigrated object in new form
			upn = module.get("UniventionOffice365userPrincipalName", "")
			value = ("defaultADconnection", upn)
			module["UniventionOffice365ADConnections"] = [value]
			self.adconnection_data = {
				"defaultADconnection": {
					"userPrincipalName": upn,
					"objectId": object_id,
				}
			}
			return

		adconnection_data_encoded = module.get("UniventionOffice365Data")
		if adconnection_data_encoded:
			try:
				self.adconnection_data = Office365Listener.decode_o365data(adconnection_data_encoded)
			except (zlib.error, TypeError):
				self.adconnection_data = {}
		else:
			self.adconnection_data = {}
		if not isinstance(self.adconnection_data, dict):
			self.adconnection_data = {}

		module["UniventionOffice365ADConnections"] = []
		adconnection_aliases = module.get("UniventionOffice365ADConnectionAlias", [])
		for adconnection in adconnection_aliases:
			try:
				upn = self.adconnection_data[adconnection]["userPrincipalName"]
			except KeyError:
				upn = ""
			value = (adconnection, upn)
			module["UniventionOffice365ADConnections"].append(value)

	def hook_ldap_addlist(self, module, al=[]):
		al = [a for a in al if a[0] != "dummyUniventionOffice365ADConnections"]
		return al

	def hook_ldap_modlist(self, module, ml=[]):
		# remove virtual dummy attribute from modlist
		ml = [m for m in ml if m[0] != "dummyUniventionOffice365ADConnections"]

		if module.get("UniventionOffice365ObjectID"):
			# unmigrated object
			return ml
		if not module.hasChanged("UniventionOffice365ADConnections"):
			return ml

		adconnection_aliases_new = set([x for x, _ in module["UniventionOffice365ADConnections"]])
		adconnections_old = module.oldinfo.get("UniventionOffice365ADConnections", [])
		adconnection_aliases_old = set([x for x, _ in adconnections_old])
		if adconnection_aliases_new == adconnection_aliases_old:
			return ml

		# Update the UniventionOffice365ADConnectionAlias list
		old = module.get("UniventionOffice365ADConnectionAlias")
		new = list(adconnection_aliases_new)
		if new != old:
			ml.append(("univentionOffice365ADConnectionAlias", old, new))

		return ml

	def hook_ldap_pre_create(self, module):
		if str2bool(module.get("UniventionOffice365Enabled")) and not module.get("mailPrimaryAddress"):
			raise univention.admin.uexceptions.valueError(msg_require_mail)

	def hook_ldap_pre_modify(self, module):
		if str2bool(module.get("UniventionOffice365Enabled")) and not module.get("mailPrimaryAddress"):
			raise univention.admin.uexceptions.valueError(msg_require_mail)
