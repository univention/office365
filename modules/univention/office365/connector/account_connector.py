# -*- coding: utf-8 -*-
#
# Univention Office 365 - account_connector
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
import pwd
import shutil
from logging import Logger

import six
from six.moves import UserDict, UserString
from typing import Dict, Tuple, List

from univention.office365 import utils
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.logging2udebug import get_logger
from univention.office365.ucr_helper import UCRHelper

# TODO move to UCRHelper
from univention.office365.udm_helper import UDMHelper
from univention.office365.utils.utils import listener_restart
'''
# Connections to Azure
Currently the connector can be configured with several connections to Azure.

The same user can be configured on multiple connections, so that on synchronization this user is replicated to associated Azure accounts
The `alias` is the name by which UCS refers to one of its connections.
Groups also maintain references to their connections, but these are not assigned directly to them but from the connections of the users they contain.

A connection depends on an `Azure Account`. The account maintains the necessary information and authorizations to be able to access the API.
The access to the API is done through a Python Wrapper of the API (MSGraphApiCore). To execute a query against the API it is necessary to have a Token,
which identifies an authorization for the account to perform the queries.

During the connector execution, the connections configured in UCS are checked.
The stored information about these connections is loaded and a `ConnectionsPool` is created with this information.

When an operation needs to be performed on a user or group, it will have a set of aliases associated with it
identifying where the information is expected to be synchronized. This set of aliases should match a subset of all the available connections.

With a pool (or sub pool) we can iterate over it and perform the operation we need through the corresponding configured connection.

If several operations need to be performed on the same connection, the pool contains a reference to the connection that is currently in use.
'''


class Connection(object):
	def __init__(self, id, account, core=None):
		# type: (str, AzureAccount, MSGraphApiCore) -> None
		self.id = id
		self.account = account
		self.core = core or MSGraphApiCore(account)


class ConnectionsPool(UserDict):
	"""
	Class to manage the connections to the AD.
	"""
	def __init__(self, logger=None):
		# type: (Logger) -> None
		if six.PY2:
			UserDict.__init__(self)
		else:
			super(ConnectionsPool, self).__init__()
		self.logger = logger or get_logger("office3365", "o365")
		self.connections = {}  # type: Dict[str, Connection]
		self.current = None

	def __iter__(self):
		# type: () -> None
		for connection in self.connections.values():
			self.current = connection
			yield connection.core
		self.current = None

	def __getitem__(self, alias):
		# type: (str) -> Connection
		return self.connections[alias]

	def __setitem__(self, alias, connection):
		# type: (str, Connection) -> None
		self.connections[alias] = connection

	def __delitem__(self, alias):
		# type: (str) -> None
		del self.connections[alias]

	def __contains__(self, alias):
		# type: (str) -> bool
		return alias in self.connections

	def __len__(self):
		# type: () -> int
		return len(self.connections)

	def status(self, only_initialized=False):
		# type: (bool) -> Tuple[str, str, str]
		for alias, connection in self.connections.items():
			confdir = connection.account.conf_dirs['CONFDIR']
			initialized = connection.account.is_initialized()
			status = 'initialized' if initialized else 'uninitialized'
			if initialized or not only_initialized:
				yield (alias, status, confdir)

	@classmethod
	def from_ucr(cls):
		# type: () -> ConnectionsPool
		"""
		Update the connections from the UCR.
		"""
		pool = None
		aliases = UCRHelper.get_adconnection_aliases().items()
		if len(aliases) > 0:
			pool = cls()
		for alias, adconnection_id in aliases:
			connection = Connection(adconnection_id, AzureAccount(alias))
			pool.connections[alias] = connection
		return pool

	def sub_pool(self, aliases):
		# type: (List[str]) -> ConnectionsPool
		"""
		Return a sub pool of the current pool.
		"""
		sub_pool = self.__class__()
		for alias in aliases:
			if alias in self.connections.keys():
				sub_pool[alias] = self[alias]
			else:
				raise KeyError('Azure AD connection alias %s is not listed in UCR %s.' % (alias, UCRHelper.alias_ucrv))
		return sub_pool

	# Only called by the script manage_adaccounts
	def create_new(self, alias, make_default=False, description="", restart_listener=True):
		# type: (str, bool, str, bool) -> None
		if alias in self:
			self.logger.error('Azure AD connection alias %s is already listed in UCR %s.', alias, UCRHelper.alias_ucrv)
			return None
		new_account = AzureAccount.create_local(alias)
		UCRHelper.set_ucr_for_new_connection(alias, make_default)
		self[alias] = Connection(new_account["adconnection_id"], new_account)

		# update in udm directory
		UDMHelper().create_udm_adconnection(alias, description)

		# set the needed variable in UCR for UMC
		UCRHelper.configure_wizard_for_adconnection(alias)
		if restart_listener:
			listener_restart()

	def rename(self, old_alias, new_alias):
		# type: (str, str) -> None
		if new_alias in self.connections.keys():
			self.logger.error('Azure AD connection alias %s is already listed in UCR %s.', new_alias, UCRHelper.alias_ucrv)
			return None
		if old_alias not in self.connections.keys():
			self.logger.error('Azure AD connection alias %s is not listed in UCR %s.', old_alias, UCRHelper.adconnection_alias_ucrv)
			return None
		if old_alias in self.connections.keys():
			self.logger.error('Azure AD connection alias %s is already configured in UCR %s, cannot rename Azure AD connection %s.', new_alias, UCRHelper.adconnection_alias_ucrv, old_adconnection_alias)
			return None
		new_adconnection_path = os.path.join(AzureAccount.config_base_path, new_alias)
		if os.path.exists(new_adconnection_path):
			self.logger.error('The path for the target Azure AD connection name %s already exists, but no UCR configuration for the Azure AD connection was found.', new_adconnection_path)
			return None
		old_adconnection_path = os.path.join(AzureAccount.config_base_path, old_alias)
		if not os.path.exists(old_adconnection_path):
			self.logger.error('The path for the old Azure AD connection %s does not exist.', old_adconnection_path)
			return None

		shutil.move(old_adconnection_path, new_adconnection_path)

		UCRHelper.rename_adconnection(old_adconnection_path, new_adconnection_path)
		listener_restart()

		self.connections[new_alias] = self.connections[old_alias]
		del self.connections[old_alias]

	def remove(self, alias):
		# type: (str) -> None
		# Checks
		if alias not in self.connections.keys():
			self.logger.error('Azure AD connection alias %s is not listed in UCR %s.', alias, UCRHelper.adconnection_alias_ucrv)
			return None

		target_path = os.path.join(AzureAccount.config_base_path, alias)
		if not os.path.exists(target_path):
			self.logger.warning('Configuration files for the Azure AD connection in %s do not exist. Removing Azure AD connection anyway...', target_path)

		UDMHelper().remove_udm_adconnection(alias)
		shutil.rmtree(target_path)
		UCRHelper.remove_adconnection(alias)
		listener_restart()


class AccountConnector(object):
	def __init__(self, logger=None):
		# type: (Logger) -> None
		self.logger = logger or get_logger("office365", "o365")

	@staticmethod
	def get_adconnections(only_initialized=False):
		# type: (bool) -> List[Tuple[str, str, str]]
		res = []
		aliases = UCRHelper.get_adconnection_aliases().items()
		for alias, adconnection_id in aliases:
			account = AzureAccount(alias)
			confdir = account.conf_dirs['CONFDIR']
			initialized = account.is_initialized()
			status = 'initialized' if initialized else 'uninitialized'
			if (only_initialized is False or initialized):
				res.append((alias, status, confdir))
		return res

	# Only called by the script manage_adconnections
	@staticmethod
	def create_new_adconnection(logger, adconnection_alias, make_default=False, description="", restart_listener=True):
		# type: (Logger, str, bool, str, bool) -> None
		aliases = UCRHelper.get_adconnection_aliases()
		if adconnection_alias in aliases:
			logger.error('Azure AD connection alias %s is already listed in UCR %s.', adconnection_alias, UCRHelper.adconnection_alias_ucrv)
			return None
		new_account = AzureAccount(adconnection_alias, lazy_load=True)
		target_path = new_account.conf_dirs['CONFDIR']
		if os.path.exists(target_path):
			logger.error('Path %s already exists, but no UCR configuration for the Azure AD connection was found.', target_path)
			return None

		# Create de needed files
		os.mkdir(target_path, 0o700)
		os.chown(target_path, pwd.getpwnam('listener').pw_uid, 0)
		for filename in ('cert.fp', 'cert.pem', 'key.pem'):
			src = os.path.join(new_account.config_base_path, filename)
			shutil.copy2(src, target_path)
			os.chown(os.path.join(target_path, filename), pwd.getpwnam('listener').pw_uid, 0)

		# update ucr with the new adconnection
		new_account.uninitialize()

		UCRHelper.set_ucr_for_new_connection(adconnection_alias, make_default)

		# update in udm directory
		UDMHelper().create_udm_adconnection(adconnection_alias, description)

		# set the needed variable in UCR for UMC
		UCRHelper.configure_wizard_for_adconnection(adconnection_alias)
		if restart_listener:
			listener_restart()

	def rename_adconnection(self, old_adconnection_alias, new_adconnection_alias):
		# type: (str, str) -> None
		aliases = UCRHelper.get_adconnection_aliases()
		if old_adconnection_alias not in aliases:
			self.logger.error('Azure AD connection alias %s is not listed in UCR %s.', old_adconnection_alias, UCRHelper.adconnection_alias_ucrv)
			return None
		if new_adconnection_alias in aliases:
			self.logger.error('Azure AD connection alias %s is already configured in UCR %s, cannot rename Azure AD connection %s.', new_adconnection_alias, UCRHelper.adconnection_alias_ucrv, old_adconnection_alias)
			return None
		new_adconnection_path = os.path.join(AzureAccount.config_base_path, new_adconnection_alias)
		if os.path.exists(new_adconnection_path):
			self.logger.error('The path for the target Azure AD connection name %s already exists, but no UCR configuration for the Azure AD connection was found.', new_adconnection_path)
			return None
		old_adconnection_path = os.path.join(AzureAccount.config_base_path, old_adconnection_alias)
		if not os.path.exists(old_adconnection_path):
			self.logger.error('The path for the old Azure AD connection %s does not exist.', old_adconnection_path)
			return None

		shutil.move(old_adconnection_path, new_adconnection_path)

		UCRHelper.rename_adconnection(old_adconnection_path, new_adconnection_path)
		listener_restart()

	def remove_adconnection(self, adconnection_alias):
		# type: (str) -> None
		aliases = UCRHelper.get_adconnection_aliases()
		# Checks
		if adconnection_alias not in aliases:
			self.logger.error('Azure AD connection alias %s is not listed in UCR %s.', adconnection_alias, UCRHelper.adconnection_alias_ucrv)
			return None

		target_path = os.path.join(AzureAccount.config_base_path, adconnection_alias)
		if not os.path.exists(target_path):
			self.logger.warning('Configuration files for the Azure AD connection in %s do not exist. Removing Azure AD connection anyway...', target_path)

		UDMHelper().remove_udm_adconnection(adconnection_alias)
		shutil.rmtree(target_path)
		UCRHelper.remove_adconnection(adconnection_alias)
		listener_restart()
