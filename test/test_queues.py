# -*- coding: utf-8 -*-
#
# Univention Office 365 - test_queues
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

import pytest

from test.utils import all_methods_called
from univention.office365.asyncqueue.queues.jsonfilesqueue import JsonFilesQueue
from univention.office365.asyncqueue.queues.redisqueue import SimpleQueue

CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))

@pytest.mark.skip("To implement")
class TestJsonFilesQueue:
	def setup(self):
		# type: () -> None
		self.queue = JsonFilesQueue(queue_name='tests_queue')
		self.queue.clear()

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, JsonFilesQueue, [])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	def test_enqueue(self):
		# type: () -> None
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2

	def test_dequeue(self):
		# type: () -> None
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2
		assert self.queue.dequeue() == {"test": "test"}
		assert self.queue.dequeue() == {"test2": "test2"}

	def test_delete_job(self):
		# type: () -> None
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2
		self.queue.delete_job("test")
		assert self.queue.len() == 1
		self.queue.delete_job("test2")
		assert self.queue.len() == 0

	def test_clear(self):
		# type: () -> None
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2
		self.queue.clear()
		assert self.queue.len() == 0


@pytest.mark.skip("To implement")
class TestRedisQueue:
	def setup(self):
		# type: () -> None
		self.queue = SimpleQueue(queue_name='tests_queue')
		self.queue.clear()

	def test_enqueue(self):
		# type: () -> None
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2
		assert self.queue.dequeue() == {"test": "test"}
		assert self.queue.dequeue() == {"test2": "test2"}


