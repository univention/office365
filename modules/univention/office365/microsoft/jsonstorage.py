# -*- coding: utf-8 -*-
#
# Univention Office 365 - jsonstorage
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


import grp
import json
import logging
import pwd
import os
from stat import S_IRUSR, S_IWUSR

from typing import Dict

from univention.office365.logging2udebug import get_logger

uid = pwd.getpwnam("listener").pw_uid
gid = grp.getgrnam("nogroup").gr_gid

class JsonStorage(object):

	def __init__(self, filename, logger=None):
		# type: (str, "logging.Logger") -> None
		self.logger = logger or get_logger("office365", "o365")
		self.filename = filename

	def read(self):
		# type: () -> Dict
		try:
			with open(self.filename, "r") as fd:
				data = json.load(fd)
		except (IOError, ValueError):
			data = dict()
		if not isinstance(data, dict):
			self.logger.error("AzureAuth._load_data(): Expected dict in file %r, got %r.", self.filename, data)
			data = dict()
		return data

	def write(self, **kwargs):
		# type: (Dict) -> None
		data = self.read()
		data.update(kwargs)
		self._save(data)

	def purge(self):
		# type: () -> None
		self._save({})

	def _save(self, data):
		# type: (Dict) -> None
		open(self.filename, "w").close()  # touch
		# os.chmod(self.filename, S_IRUSR | S_IWUSR)
		# os.chown(self.filename, self.listener_uid, 0)
		os.chmod(self.filename, 0o700)
		os.chown(self.filename, uid, gid)
		with open(self.filename, "w") as fd:
			json.dump(data, fd)
