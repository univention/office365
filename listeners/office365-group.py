from typing import Dict, Optional, List

import univention.listener

from univention.office365.connector.connector import GroupConnector
from univention.office365.ucr_helper import UCRHelper
from univention.office365.udmwrapper.udmobjects import UDMOfficeGroup
from univention.office365.logging2udebug import get_logger

logger = get_logger("office365", "o365")

connector = GroupConnector(logger=logger)


class ListenerModuleTemplate(univention.listener.ListenerModuleHandler):

	class Configuration(object):
		name = 'office365-group'
		description = 'sync groups to office 365'
		if UCRHelper.group_sync:
			ldap_filter = '(entryCSN=)'  # not matching anything, evaluated by UDL filter implementation
			logger.warn("office 365 group listener deactivated by UCR office365/groups/sync")
		elif connector.has_initialized_connections():
			ldap_filter = '(&(objectClass=posixGroup){})'.format(connector.get_listener_filter())
			logger.info("office 365 group listener active with filter=%r", ldap_filter)
		else:
			ldap_filter = '(objectClass=deactivatedOffice365GroupListener)'
			logger.warn("office 365 group listener deactivated (no initialized adconnections)")
		attributes = connector.attrs

	def __init__(self, *args, **kwargs):
		self.logger = logger
		self.connector = connector
		super(ListenerModuleTemplate, self).__init__(args, kwargs)

	def create(self, dn, new):
		# type:  (str, Dict[str, List[bytes]]) -> None
		self.logger.debug('dn: %r', dn)
		udm_group = UDMOfficeGroup(ldap_fields=new, ldap_cred=self._ldap_credentials, dn=dn, logger=logger)
		self.connector.create(udm_object=udm_group)

	def modify(self, dn, old, new, old_dn):
		# type:  (str, Dict[str, List[bytes]], Dict[str, List[bytes]], Optional[str]) -> None
		self.logger.debug('dn: %r', dn)
		new_udm_group = UDMOfficeGroup(ldap_fields=new, ldap_cred=self._ldap_credentials, dn=dn, logger=logger)
		old_udm_group = UDMOfficeGroup(ldap_fields=old, ldap_cred=self._ldap_credentials, dn=old_dn or dn, logger=logger)
		self.connector.modify(new_udm_group=new_udm_group, old_udm_group=old_udm_group)

		if old_dn:
			self.logger.debug('it is (also) a move! old_dn: %r', old_dn)
		self.logger.debug('changed attributes: %r', self.diff(old, new))

	def remove(self, dn, old):
		# type:  (str, Dict[str, List[bytes]]) -> None
		self.logger.debug('dn: %r', dn)
		udm_group = UDMOfficeGroup(ldap_fields=old, ldap_cred=self._ldap_credentials, dn=dn, logger=logger)
		self.connector.delete(udm_object=udm_group)
