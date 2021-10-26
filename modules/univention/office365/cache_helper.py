#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Copyright 2021 Univention GmbH
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

from contextlib import contextmanager
from pwd import getpwnam
import os

import gdbm as gdbm


class Cache(object):
	def __init__(self, db_file):
		self.db_file = db_file
		self._listenr_uid = getpwnam('listener').pw_uid

	@contextmanager
	def writing_db(self, mode):
		db = gdbm.open(self.db_file, mode)
		os.chown(self.db_file, self._listenr_uid, -1)
		yield db
		db.close()

	def save(self, key, values):
		key = key.encode('utf-8').lower()
		values = ', '.join(values)
		with self.writing_db('csu') as db:
			db[key] = values

	def clear(self):
		with self.writing_db('n'):
			pass

	def delete(self, key):
		key = key.encode('utf-8').lower()
		with self.writing_db('csu') as db:
			try:
				del db[key]
			except KeyError:
				pass

	def load(self):
		try:
			db = gdbm.open(self.db_file)
		except EnvironmentError:
			return {}
		else:
			ret = dict(db)
			db.close()
			return ret


GROUP_USERS = Cache('/usr/share/univention-office365/o365-group-users.db')
USER_AZURES = Cache('/usr/share/univention-office365/o365-user-azures.db')
GROUP_GROUPS = Cache('/usr/share/univention-office365/o365-group-groups.db')


def current_caches():
	return GROUP_USERS.load(), USER_AZURES.load(), GROUP_GROUPS.load()


def azure_relevant_for_group(azure_name, group_dn, caches=None):
	if caches:
		group_users, user_azures, group_groups = caches
	else:
		group_users, user_azures, group_groups = current_caches()
	for user in group_users.get(group_dn.lower(), '').split(', '):
		if not user:
			continue
		if azure_name in user_azures.get(user.lower(), '').split(', '):
			return True
	for group in group_groups.get(group_dn.lower(), '').split(', '):
		if not group:
			continue
		if azure_relevant_for_group(azure_name, group, [group_users, user_azures, group_groups]):
			return True
	return False
