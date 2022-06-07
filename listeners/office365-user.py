from typing import Dict, Optional, List

import univention.listener

from univention.office365.connector.connector import UserConnector
from univention.office365.udm_helper import UDMHelper
from univention.office365.udmwrapper.udmobjects import UDMOfficeUser
from univention.office365.logging2udebug import get_logger

logger = get_logger("office365", "o365-user")

connector = UserConnector(logger=logger)


class ListenerModuleTemplate(univention.listener.ListenerModuleHandler):

	class Configuration(object):
		name = 'office365-user'
		description = 'sync users to office 365'
		if connector.has_initialized_connections():
			ldap_filter = '(&(objectClass=posixAccount)(objectClass=univentionOffice365)(uid=*){})'.format(connector.get_listener_filter())
			logger.info("office 365 user listener active with filter=%r", ldap_filter)
		else:
			ldap_filter = '(objectClass=deactivatedOffice365UserListener)'  # "objectClass" is indexed
			logger.warning("office 365 user listener deactivated (no initialized AD connection)")
		attributes = connector.attrs.all

	def __init__(self, *args, **kwargs):
		self.logger = logger
		self.connector = connector
		super(ListenerModuleTemplate, self).__init__(args, kwargs)

	def pre_run(self):
		if self._ldap_credentials:
			UDMHelper.ldap_cred = self._ldap_credentials

	def create(self, dn, new):
		# type:  (str, Dict[str, List[bytes]]) -> None
		self.logger.info('create dn: %r', dn)
		udm_user = UDMOfficeUser(ldap_fields=new, ldap_cred=self._ldap_credentials, dn=dn, logger=logger)
		if udm_user.should_sync():
			self.connector.create(udm_object=udm_user)

	def modify(self, dn, old, new, old_dn):
		# type:  (str, Dict[str, List[bytes]], Dict[str, List[bytes]], Optional[str]) -> None
		self.logger.info('modify dn: %r', dn)
		new_udm_user = UDMOfficeUser(ldap_fields=new, ldap_cred=self._ldap_credentials, dn=dn, logger=logger)
		old_udm_user = UDMOfficeUser(ldap_fields=old, ldap_cred=self._ldap_credentials, dn=old_dn or dn, logger=logger)
		self.connector.modify(new_object=new_udm_user, old_object=old_udm_user)

		if old_dn:
			self.logger.debug('it is (also) a move! old_dn: %r', old_dn)
		self.logger.debug('changed attributes: %r', self.diff(old, new))

	def remove(self, dn, old):
		# type:  (str, Dict[str, List[bytes]]) -> None
		self.logger.info('remove dn: %r', dn)
		udm_user = UDMOfficeUser(ldap_fields=old, ldap_cred=self._ldap_credentials, dn=dn, logger=logger)
		if udm_user.should_sync():
			self.connector.delete(udm_object=udm_user)
