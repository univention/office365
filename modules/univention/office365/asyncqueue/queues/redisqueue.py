# -*- coding: utf-8 -*-
#
# Univention Office 365 - redisqueue
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


import pickle

import redis
from typing import Optional, Any

from univention.office365.asyncqueue.queues.asyncqueue import AbstractQueue


class RedisQueue(AbstractQueue):
	def __init__(self, queue_name, redis_client):
		# type: (str, redis.Redis) -> None
		super(RedisQueue, self).__init__(queue_name)
		self.redis_client = redis_client or redis.Redis()

	def push(self, item):
		# type: (Any) -> None
		self.redis_client.rpush(self.name, pickle.dumps(item))

	def pop(self):
		# type: () -> Any
		return pickle.loads(self.redis_client.brpop(self.name))

	def __len__(self):
		# type: () -> int
		return self.redis_client.llen(self.name)



class SimpleQueue(AbstractQueue):
	def __init__(self, queue_name, conn=None):
		# type: (str, Optional[Any]) -> None
		self.conn = conn or redis.Redis()
		self.name = queue_name

	def clear(self):
		# type: () -> None
		self.conn.delete(self.name)

	def __len__(self):
		# type: () -> int
		return self.conn.llen(self.name)

	def enqueue(self, task):
		# type: (Any) -> Any
		serialized_task = pickle.dumps(task, protocol=pickle.HIGHEST_PROTOCOL)
		self.conn.lpush(self.name, serialized_task)
		return task

	def dequeue(self, process_task=False):
		# type: (bool) -> Any
		_, serialized_task = self.conn.brpop(self.name)
		task = pickle.loads(serialized_task)
		if process_task:
			task.process()
		return task

	def get_length(self):
		# type: () -> int
		return self.conn.llen(self.name)
