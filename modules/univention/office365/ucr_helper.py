# -*- coding: utf-8 -*-
#
# Univention Office 365 - ucr_helper
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


import os
import re
import subprocess
from logging import Logger
from typing import Dict, Optional, Callable, List
from functools import wraps

from univention.config_registry import ConfigRegistry, handler_set, handler_unset
from univention.config_registry.frontend import ucr_update


def pre_post_decorator(pre_name=None, post_name=None):
	def decorator(f):
		@wraps(f)
		def wrapper(self, *args, **kw):
			if pre_name and hasattr(self, pre_name) and isinstance(getattr(self, pre_name), Callable):
				getattr(self, pre_name)()
			result = f(self, *args, **kw)
			if post_name and hasattr(self, post_name) and isinstance(getattr(self, post_name), Callable):
				getattr(self, post_name)()
			return result
		return wrapper
	return decorator


class UCRHelperC(ConfigRegistry):
	group_sync_ucrv = "office365/groups/sync"
	adconnection_filter_ucrv = 'office365/adconnection/filter'
	adconnection_alias_ucrv = 'office365/adconnection/alias/'
	adconnection_wizard_ucrv = 'office365/adconnection/wizard'
	usage_location_ucrv = "office365/attributes/usageLocation"
	ssl_country_ucrv = "ssl/country"
	office365_migrate_adconnection_ucrv = 'office365/migrate/adconnectionalias'
	default_adconnection_alias_ucrv = 'office365/defaultalias'
	default_adconnection_name = "defaultADconnection"
	default_azure_service_plan_names = "SHAREPOINTWAC, SHAREPOINTWAC_DEVELOPER, OFFICESUBSCRIPTION, OFFICEMOBILE_SUBSCRIPTION, SHAREPOINTWAC_EDU"

	@pre_post_decorator(pre_name="load")
	def ucr_split_value(self, key):
		# type: (str) -> list
		"""
		Returns a list of values for a UCR key.
		key = "value1, value2, value3 "
		returns ["value1", "value2", "value3"]
		"""
		return [x.strip() for x in self.get(key, "").strip().split(",") if x.strip()]

	@pre_post_decorator(pre_name="load")
	def ucr_entries_to_dict(self, key_pattern):
		# type: (str) -> Dict
		"""
		Returns a dict of UCR entries for a given key pattern.
		key/pattern/asdf1 = "value1"
		key/pattern/asdf2 = "value2"
		key/pattern/asdf3 = "value3"
		returns {"asdf1": "value1", "asdf2": "value2", "asdf3": "value3"}
		"""
		return {k.split("/")[-1]: v.strip() for k, v in self.items() if k.startswith(key_pattern)}

	@pre_post_decorator(pre_name="load")
	def get_adconnection_aliases(self):
		# type: () -> Dict
		"""
		Extract the AD connection aliases from UCR. Name of the ad connection is the key and ('initialized' or 'uninitialized') is the value.
		@return: dict filtered with only ad connection aliases
		"""
		return {k[len(self.adconnection_alias_ucrv):]: v for k, v in self.items() if k.startswith(self.adconnection_alias_ucrv)}

	@pre_post_decorator(pre_name="load")
	def get_adconnection_filtered_in(self):
		"""
		Returns a list of AD connections that are filtered in.
		"""
		ucr_value = self[self.adconnection_filter_ucrv] or ''
		return ucr_value.strip().split()

	@pre_post_decorator(post_name="load")
	def set_ucs_overview_link(self):
		sp_query_string = "?spentityid=urn:federation:MicrosoftOnline"
		sp_link = "https://{}/simplesamlphp/saml2/idp/SSOService.php{}".format(self["ucs/server/sso/fqdn"], sp_query_string)
		ucr_update(self, {
			"ucs/web/overview/entries/service/office365/description": "Single Sign-On login for Microsoft 365",
			"ucs/web/overview/entries/service/office365/label": "Microsoft 365 Login",
			"ucs/web/overview/entries/service/office365/link": sp_link,
			"ucs/web/overview/entries/service/office365/description/de": "Single-Sign-On Link für Microsoft 365",
			"ucs/web/overview/entries/service/office365/label/de": "Microsoft 365 Login",
			"ucs/web/overview/entries/service/office365/priority": "50",
			"ucs/web/overview/entries/service/office365/icon": "/office365.png"
		})

	@pre_post_decorator(post_name="load")
	def rename_adconnection(self, old_adconnection_alias, new_adconnection_alias):
		ucrv_set = '{}={}'.format('%s%s' % (self.adconnection_alias_ucrv, new_adconnection_alias), self.ucr.get('%s%s' % (self.adconnection_alias_ucrv, old_adconnection_alias)))
		handler_set([ucrv_set])
		ucrv_unset = '%s%s' % (self.adconnection_alias_ucrv, old_adconnection_alias)
		handler_unset([ucrv_unset])

	@pre_post_decorator(post_name="load")
	def set_ucr_for_new_connection(self, adconnection_alias, make_default, value="uninitialized"):
		# type: (str, bool, str) -> None
		ucrv = ['{}{}={}'.format(self.adconnection_alias_ucrv, adconnection_alias, value)]
		if make_default:
			ucrv.append('{}={}'.format(self.default_adconnection_alias_ucrv, adconnection_alias))
		handler_set(ucrv)

	@pre_post_decorator(post_name="load")
	def remove_adconnection(self, adconnection_alias):
		ucrv_unset = '%s%s' % (self.adconnection_alias_ucrv, adconnection_alias)
		handler_unset([ucrv_unset])

	@property
	@pre_post_decorator(pre_name="load")
	def group_sync(self):
		# type: () -> bool
		return self.is_true(self.group_sync_ucrv, False)

	@pre_post_decorator(pre_name="load")
	def get_service_plan_names(self):
		# type: () -> List[str]
		ucr_service_plan_names = self.get("office365/subscriptions/service_plan_names") or self.default_azure_service_plan_names
		return [spn.strip() for spn in ucr_service_plan_names.split(",")]

	@pre_post_decorator(post_name="load")
	def configure_wizard_for_adconnection(self, adconnection_alias):
		# type: (str) -> None
		# configure UCR to let wizard configure this adconnection
		# TODO: Should be removed in the future, as the wizard should be able to configure
		# adconnections by itself
		ucrv_set = '{}={}'.format(self.adconnection_wizard_ucrv, adconnection_alias)
		handler_set([ucrv_set])
		subprocess.call(['pkill', '-f', '/usr/sbin/univention-management-console-module -m office365'])

	@pre_post_decorator(pre_name="load")
	def adconnection_wizard(self):
		# type: () -> str
		return self.get(self.adconnection_wizard_ucrv) or None

	def adconnection_id_to_alias(self, logger, adconnection_id):
		# type: (method, str) -> Optional[str]
		for alias, t_id in self.get_adconnection_aliases().items():
			if t_id == adconnection_id:
				return alias
		logger.error('Unknown Azure AD connection ID %r.', adconnection_id)
		return None

	@pre_post_decorator(pre_name="load")
	def get_http_proxies(self, logger):
		# type: (Logger) -> Dict[str,str]
		res = dict()
		# 1. proxy settings from environment
		for req_key, env_key in [('http', 'HTTP_PROXY'), ('http', 'http_proxy'), ('https', 'HTTPS_PROXY'), ('https', 'https_proxy')]:
			try:
				res[req_key] = os.environ[env_key]
			except KeyError:
				pass
		# 2. settings from system wide UCR proxy settings
		for req_key, ucrv in [('http', 'proxy/http'), ('https', 'proxy/https')]:
			if self.get(ucrv):
				res[req_key] = self[ucrv]

		# 3. settings from office365 UCR proxy settings
		for req_key, ucrv in [('http', 'office365/proxy/http'), ('https', 'office365/proxy/https')]:
			if self.get(ucrv) == 'ignore':
				try:
					del res[req_key]
				except KeyError:
					pass
			elif self.get(ucrv):
				res[req_key] = self[ucrv]
		# remove password from log output
		res_redacted = res.copy()
		for k, v in res_redacted.items():
			password = re.findall(r'http.?://\w+:(\w+)@.*', v)
			if password:
				res_redacted[k] = v.replace(password[0], '*****', 1)

		logger.debug('proxy settings: %r', res_redacted)
		return res

	@pre_post_decorator(pre_name="load")
	def get_usage_location(self):
		# type: () -> str
		res = self.get(self.usage_location_ucrv) or self.get(self.ssl_country_ucrv)
		if not res or len(res) != 2:
			raise RuntimeError("Invalid usageLocation '{}' - user cannot be created.".format(res))
		return res

	@pre_post_decorator(pre_name="load")
	def get_default_adconnection(self):
		# type: () -> Optional[str]
		return self.get(self.default_adconnection_alias_ucrv)

	@pre_post_decorator(pre_name="load")
	def get_ucs_sso_fqdn(self):
		# type: () -> str
		return self.get('ucs/server/sso/fqdn', "%s.%s" % (self.get('hostname', 'undefined'), self.get('domainname', 'undefined')))

	@pre_post_decorator(pre_name="load")
	def get_domainname(self):
		# type: () -> str
		return self.get('domainname', 'undefined')
	
	@pre_post_decorator(pre_name="load")
	def get_saml_certificate(self, default=None):
		# type: (Optional[str]) -> str
		return self.get('saml/idp/certificate/certificate', default)
	
	@pre_post_decorator(pre_name="load")
	def get_ssohost(self):
		# type: () -> str
		return self.get('ucs/server/sso/fqdn', 'ucs-sso.{domain}'.format(domain=self.get('domainname')))

"""
Singleton instance
A module is only loaded once, so we can use an instance defined here as a singleton.
To decide on what to use for singleton: https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python
"""
UCRHelper = UCRHelperC()
UCRHelper.load()
