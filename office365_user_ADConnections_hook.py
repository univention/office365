# -*- coding: utf-8 -*-
#
# Univention Office 365 - UDM hook to access ADConnection data
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
from univention.lib.i18n import Translation
from univention.office365.listener import Office365Listener

_ = Translation('univention-admin-handlers-office365').translate


class Office365ADConnectionsHook(simpleHook):
	type = "Office365ADConnectionsHook"

	def hook_open(self, module):
		object_id = module.get("UniventionOffice365ObjectID")
		if object_id:
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
		if not adconnection_data_encoded:
			self.adconnection_data = {}
			return

		self.adconnection_data = Office365Listener.decode_o365data(adconnection_data_encoded)
		module["UniventionOffice365ADConnections"] = []
		if isinstance(self.adconnection_data, dict):
			for adconnection, data in self.adconnection_data.iteritems():
				try:
					upn = data["userPrincipalName"]
				except KeyError:
					upn = ""
				value = (adconnection, upn)
				module["UniventionOffice365ADConnections"].append(value)
		else:
			self.adconnection_data = {}

	def hook_ldap_modlist(self, module, ml=[]):
		# remove virtual dummy attribute from modlist
		ml = [m for m in ml if m[0] != "dummyUniventionOffice365ADConnections"]

		if module.get("UniventionOffice365ObjectID"):
			return ml
		if not module.hasChanged("UniventionOffice365ADConnections"):
			return ml

		adconnection_aliases_new = set([x for x, _ in module["UniventionOffice365ADConnections"]])
		adconnections_old = module.oldinfo.get("UniventionOffice365ADConnections", [])
		adconnection_aliases_old = set([x for x, _ in adconnections_old])
		if adconnection_aliases_new == adconnection_aliases_old:
			return ml

		## Update the UniventionOffice365ADConnectionAlias list
		old = module.get("UniventionOffice365ADConnectionAlias")
		new = list(adconnection_aliases_new)
		ml.append(("univentionOffice365ADConnectionAlias", old, new))

		## Update the UniventionOffice365Data
		new_adconnection_data = {}
		for adconnection in adconnection_aliases_new:
			try:
				new_adconnection_data[adconnection] = self.adconnection_data[adconnection]
			except KeyError:
				new_adconnection_data[adconnection] = {}

		## keep objectId for removed connections but remove userPrincipalName:
		connections_to_be_deleted = adconnection_aliases_old - adconnection_aliases_new
		for adconnection in connections_to_be_deleted:
			new_adconnection_data[adconnection] = self.adconnection_data[adconnection]
			try:
				del new_adconnection_data[adconnection]["userPrincipalName"]
			except KeyError:
				pass

		if new_adconnection_data != self.adconnection_data:
			old = module.oldinfo.get("UniventionOffice365Data")
			new = Office365Listener.encode_o365data(new_adconnection_data)
			ml.append(("univentionOffice365Data", old, new))
		return ml
