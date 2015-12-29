# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module impl
#
# Copyright 2015 Univention GmbH
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

from operator import itemgetter
import uuid

import univention.admin.uldap
import univention.admin.objects
from univention.office365.azure_auth import log_a, log_e, log_ex, log_p
from univention.office365.azure_handler import AzureHandler


class Office365Listener(AzureHandler):
	def __init__(self, listener, name, attrs):
		super(Office365Listener, self).__init__(listener, name)
		self.attrs = attrs

	@property
	def verified_domains(self):
		return map(itemgetter("name"), self.list_verified_domains())

	def _anonymize(self, txt):
		return uuid.uuid4().get_hex()

	def _get_udm_attributes_and_values(self, attrs, user):
		# anonymize > static > sync
		res = dict()
		for attr in attrs:
			if attr not in user:
				# user has attribute not set
				continue

			if attr in self.attrs["anonymize"]:
				res[attr] = self._anonymize(user[attr][0])  # TODO: multiple value attributes
			elif attr in self.attrs["static"]:
				res[attr] = self.attrs["static"][attr]
			elif attr in self.attrs["sync"]:
				res[attr] = user[attr][0]  # TODO: multiple value attributes
			else:
				raise RuntimeError("Attribute to sync '{}' is not configured through UCR.".format(attr))
		return res

	def create_user(self, new):
		attributes = {
			"immutableId": new["entryUUID"][0],
			"accountEnabled": True,
			"passwordProfile": {
				"password": "univention.99",
				"forceChangePasswordNextLogin": False},
		}
		all_attrs = list(self.attrs["anonymize"])
		all_attrs.extend(self.attrs["static"])
		all_attrs.extend(self.attrs["sync"])
		udm_attrs = self._get_udm_attributes_and_values(all_attrs, new)

		for k, v in udm_attrs.items():
			attributes[self.attrs["mapping"][k]] = v


		# mandatory attributes
		attributes["userPrincipalName"] = "{0}@{1}".format(new["uid"][0], self.verified_domains[0])  # TODO: make the domain choosable
		attributes["mailNickname"] = new["uid"][0]
		if "displayName" not in attributes:
			attributes["displayName"] = "no name"

		log_p("Creating user with attributes: {}...".format(attributes))
		super(Office365Listener, self).create_user(attributes)

		user = self.list_users(ofilter="userPrincipalName eq '{}'".format(attributes["userPrincipalName"]))
		if user["value"]:
			return user["value"][0]
		else:
			raise RuntimeError("Created user '{}' cannot be retrieved.".format(attributes["userPrincipalName"]))

	def delete_user(self, old):
		return super(Office365Listener, self).delete_user(old["univentionOffice365ObjectID"][0])

	def get_udm_user(self, ldap_cred, userdn):
		lo = univention.admin.uldap.access(
			host=ldap_cred["ldapserver"],
			base=ldap_cred["basedn"],
			binddn=ldap_cred["binddn"],
			bindpw=ldap_cred["bindpw"])
		po = univention.admin.uldap.position(self.listener.configRegistry["ldap/base"])
		univention.admin.modules.update()
		usersmod = univention.admin.modules.get("users/user")
		univention.admin.modules.init(lo, po, usersmod)
		user = usersmod.object(None, lo, po, userdn)
		user.open()
		return user
