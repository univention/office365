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
import random
import string

import univention.admin.uldap
import univention.admin.objects
from univention.office365.azure_auth import log_a, log_e, log_ex, log_p
from univention.office365.azure_handler import AzureHandler


class Office365Listener():
	def __init__(self, listener, name, attrs):
		self.ah = AzureHandler(listener, name)
		self.listener = listener
		self.attrs = attrs

	@property
	def verified_domains(self):
		return map(itemgetter("name"), self.ah.list_verified_domains())

	def _get_sync_values(self, attrs, user):
		# anonymize > static > sync
		res = dict()
		for attr in attrs:
			if attr not in user or attr == "univentionOffice365Enabled":
				# user has attribute not set | ignore univentionOffice365Enabled
				continue

			if attr in self.attrs["anonymize"]:
				tmp = map(Office365Listener._anonymize, user[attr])
			elif attr in self.attrs["static"]:
				tmp = [self.attrs["static"][attr]]
			elif attr in self.attrs["sync"]:
				tmp = user[attr]
			else:
				raise RuntimeError("Attribute to sync '{}' is not configured through UCR.".format(attr))

			if attr in res:
				if isinstance(res[attr], list):
					res[attr].append(tmp)
				else:
					raise RuntimeError(
						"Office365Listener._get_sync_values() res[{}] already exists with type {} and value '{}'.".format(
							attr,
							type(res[attr]),
							res[attr]))
			else:
				if len(tmp) == 1:
					res[attr] = tmp[0]
				else:
					res[attr] = tmp
		return res

	def create_user(self, new):
		udm_attrs = self._get_sync_values(self.attrs["listener"], new)

		attributes = dict()
		for k, v in udm_attrs.items():
			azure_ldap_attribute_name = self.attrs["mapping"][k]
			if azure_ldap_attribute_name in attributes:
				if isinstance(v, list):
					list_method = list.extend
				else:
					list_method = list.append
				if not isinstance(attributes[azure_ldap_attribute_name], list):
					attributes[azure_ldap_attribute_name] = [attributes[azure_ldap_attribute_name]]
				list_method(attributes[azure_ldap_attribute_name], v)
			else:
				attributes[azure_ldap_attribute_name] = v

		# mandatory attributes, not to be overwritten by user
		mandatory_attributes = dict(
			immutableId=new["entryUUID"][0],
			accountEnabled=True,
			passwordProfile=dict(
				password=u"".join(Office365Listener._get_random_pw()),
				forceChangePasswordNextLogin=False
			),
			userPrincipalName="{0}@{1}".format(new["uid"][0], self.verified_domains[0]),  # TODO: make the domain choosable
			mailNickname=new["uid"][0],
			displayName=attributes["displayName"] if "displayName" in attributes else "no name"
		)
		attributes.update(mandatory_attributes)

		self.ah.create_user(attributes)

		user = self.ah.list_users(ofilter="userPrincipalName eq '{}'".format(attributes["userPrincipalName"]))
		if user["value"]:
			return user["value"][0]
		else:
			raise RuntimeError("Office365Listener.create_user() created user '{}' cannot be retrieved.".format(attributes["userPrincipalName"]))

	def delete_user(self, old):
		return self.ah.delete_user(old["univentionOffice365ObjectID"][0])

	def deactivate_user(self, old):
		return self.ah.deactivate_user(old["univentionOffice365ObjectID"][0])

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

	def modify_user(self, old, new):
		modifications = [attr for attr in self.attrs["listener"]
			if attr in new and attr not in old or
			attr in old and attr not in new or
			(attr in old and attr in new and old[attr] != new[attr])
		]
		if modifications:
			log_a("Office365Listener.modify_user() modifications={}".format(modifications))

			udm_attrs = self._get_sync_values(modifications, new)

			attributes = dict()
			for k, v in udm_attrs.items():
				attributes[self.attrs["mapping"][k]] = v

			object_id = new["univentionOffice365ObjectID"][0]
			return self.ah.modify_user(object_id=object_id, modifications=attributes)
		else:
			log_a("Office365Listener.modify_user() no modifications - nothing to do.")
			return

	def get_user(self, user):
		"""
		fetch Azure user object
		:param user: listener old or new
		:return: dict
		"""
		object_id = user["univentionOffice365ObjectID"][0]
		if not object_id:
			upn = "{0}@{1}".format(user["uid"][0], self.verified_domains[0]),  # TODO: make the domain choosable
			user = self.ah.list_users(ofilter="userPrincipalName eq '{}'".format(upn))
			if user["value"]:
				object_id = user["value"][0]["objectId"]
		return self.ah.list_users(objectid=object_id)

	@staticmethod
	def _anonymize(txt):
		return uuid.uuid4().get_hex()

	@staticmethod
	def _get_random_pw():
		# have at least one char from each category in password
		# https://msdn.microsoft.com/en-us/library/azure/jj943764.aspx
		pw = list(random.choice(string.lowercase))
		pw.append(random.choice(string.uppercase))
		pw.append(random.choice(string.digits))
		pw.append(random.choice(u"@#$%^&*-_+=[]{}|\:,.?/`~();"))
		pw.extend(random.choice(string.ascii_letters + string.digits + u"@#$%^&*-_+=[]{}|\:,.?/`~();") for _ in range(12))
		random.shuffle(pw)
		return pw
