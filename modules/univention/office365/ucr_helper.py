import subprocess
from typing import Dict

from univention.config_registry import ConfigRegistry, handler_set, handler_unset
from univention.config_registry.frontend import ucr_update


class UCRHelperC(ConfigRegistry):
	group_sync_ucrv = "office365/groups/sync"
	adconnection_filter_ucrv = 'office365/adconnection/filter'
	adconnection_alias_ucrv = 'office365/adconnection/alias/'
	adconnection_wizard_ucrv = 'office365/adconnection/wizard'
	office365_migrate_adconnection_ucrv = 'office365/migrate/adconnectionalias'
	default_adconnection_alias_ucrv = 'office365/defaultalias'
	default_adconnection_name = "defaultADconnection"
	default_azure_service_plan_names = "SHAREPOINTWAC, SHAREPOINTWAC_DEVELOPER, OFFICESUBSCRIPTION, OFFICEMOBILE_SUBSCRIPTION, SHAREPOINTWAC_EDU"



	def ucr_split_value(self, key):
		# type: (str) -> list
		"""
		Returns a list of values for a UCR key.
		key = "value1, value2, value3 "
		returns ["value1", "value2", "value3"]
		"""
		return [x.strip() for x in self.get(key).strip().split(",") if x.strip()]

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

	def get_adconnection_aliases(self):
		# type: () -> Dict
		"""
		Extract the AD connection aliases from UCR. Name of the ad connection is the key and ('initialized' or 'uninitialized') is the value.
		@return: dict filtered with only ad connection aliases
		"""
		return {k[len(self.adconnection_alias_ucrv):]: v for k, v in self.items() if k.startswith(self.adconnection_alias_ucrv)}

	def get_adconnection_filtered_in(self):
		"""
		Returns a list of AD connections that are filtered in.
		"""
		ucr_value = self[self.adconnection_filter_ucrv] or ''
		return ucr_value.strip().split()

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

	def rename_adconnection(self, old_adconnection_alias, new_adconnection_alias):
		ucrv_set = '{}={}'.format('%s%s' % (self.adconnection_alias_ucrv, new_adconnection_alias), self.ucr.get('%s%s' % (self.adconnection_alias_ucrv, old_adconnection_alias)))
		handler_set([ucrv_set])
		ucrv_unset = '%s%s' % (self.adconnection_alias_ucrv, old_adconnection_alias)
		handler_unset([ucrv_unset])

	def set_ucr_for_new_connection(self, adconnection_alias, make_default, value="uninitialized"):
		# type: (str, bool, str) -> None
		ucrv = ['{}{}={}'.format(self.adconnection_alias_ucrv, adconnection_alias, value)]
		if make_default:
			ucrv.append('{}={}'.format(self.default_adconnection_alias_ucrv, adconnection_alias))
		handler_set(ucrv)

	def remove_adconnection(self, adconnection_alias):
		ucrv_unset = '%s%s' % (self.adconnection_alias_ucrv, adconnection_alias)
		handler_unset([ucrv_unset])

	@property
	def group_sync(self):
		# type: () -> bool
		return self.is_true(self.group_sync_ucrv, False)

	def get_service_plan_names(self):
		ucr_service_plan_names = self.get("office365/subscriptions/service_plan_names") or self.default_azure_service_plan_names
		return [spn.strip() for spn in ucr_service_plan_names.split(",")]

	def configure_wizard_for_adconnection(self, adconnection_alias):
		# configure UCR to let wizard configure this adconnection
		# TODO: Should be removed in the future, as the wizard should be able to configure
		# adconnections by itself
		ucrv_set = '{}={}'.format(self.adconnection_wizard_ucrv, adconnection_alias)
		handler_set([ucrv_set])
		subprocess.call(['pkill', '-f', '/usr/sbin/univention-management-console-module -m office365'])

	def adconnection_wizard(self):
		# type: () -> str
		return self.get(self.adconnection_wizard_ucrv) or None
"""
Singleton instance
A module is only loaded once, so we can use an instance defined here as a singleton.
To decide on what to use for singleton: https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python
"""
UCRHelper = UCRHelperC()
