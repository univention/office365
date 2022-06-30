# -*- coding: utf-8 -*-
#
# Univention Office 365 - office365-group
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

from __future__ import absolute_import
from typing import Dict, Optional, List

import univention.listener

from univention.office365.connector.connector import GroupConnector
from univention.office365.ucr_helper import UCRHelper
from univention.office365.udm_helper import UDMHelper
from univention.office365.udmwrapper.udmobjects import UDMOfficeGroup
from univention.office365.logging2udebug import get_logger

logger = get_logger("office365", "o365-group")

connector = GroupConnector(logger=logger)


class ListenerModuleTemplate(univention.listener.ListenerModuleHandler):

	class Configuration(object):
		name = 'office365-group'
		description = 'sync groups to office 365'
		if not UCRHelper.group_sync:
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

	def pre_run(self):
		if self._ldap_credentials:
			UDMHelper.ldap_cred = self._ldap_credentials

	def create(self, dn, new):
		# type:  (str, Dict[str, List[bytes]]) -> None
		self.logger.info('create dn: %r', dn)
		udm_group = UDMOfficeGroup(ldap_fields=new, ldap_cred=self._ldap_credentials, dn=dn, logger=logger)
		self.connector.create(udm_object=udm_group)

	def modify(self, dn, old, new, old_dn):
		# type:  (str, Dict[str, List[bytes]], Dict[str, List[bytes]], Optional[str]) -> None
		self.logger.info('modify dn: %r', dn)
		new_udm_group = UDMOfficeGroup(ldap_fields=new, ldap_cred=self._ldap_credentials, dn=dn, logger=logger)
		old_udm_group = UDMOfficeGroup(ldap_fields=old, ldap_cred=self._ldap_credentials, dn=old_dn or dn, logger=logger)
		self.connector.modify(old_udm_group=old_udm_group, new_udm_group=new_udm_group)

		if old_dn:
			self.logger.debug('it is (also) a move! old_dn: %r', old_dn)
		self.logger.debug('changed attributes: %r', self.diff(old, new))

	def remove(self, dn, old):
		# type:  (str, Dict[str, List[bytes]]) -> None
		self.logger.info('remove dn: %r', dn)
		udm_group = UDMOfficeGroup(ldap_fields=old, ldap_cred=self._ldap_credentials, dn=dn, logger=logger)
		self.connector.delete(udm_object=udm_group)
