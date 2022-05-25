import os

import pytest

from test.utils import all_methods_called
from univention.office365.asyncqueue.queues.jsonfilesqueue import JsonFilesQueue
from univention.office365.asyncqueue.queues.redisqueue import SimpleQueue

CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))

@pytest.mark.skip("To implement")
class TestJsonFilesQueue:
	def setup(self):
		self.queue = JsonFilesQueue(queue_name='tests_queue')
		self.queue.clear()

	def test_completity(self):
		diff = all_methods_called(self.__class__, JsonFilesQueue, [])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	def test_enqueue(self):
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2

	def test_dequeue(self):
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2
		assert self.queue.dequeue() == {"test": "test"}
		assert self.queue.dequeue() == {"test2": "test2"}

	def test_delete_job(self):
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2
		self.queue.delete_job("test")
		assert self.queue.len() == 1
		self.queue.delete_job("test2")
		assert self.queue.len() == 0

	def test_clear(self):
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2
		self.queue.clear()
		assert self.queue.len() == 0


@pytest.mark.skip("To implement")
class TestRedisQueue:
	def setup(self):
		self.queue = SimpleQueue(queue_name='tests_queue')
		self.queue.clear()

	def test_enqueue(self):
		self.queue.enqueue({"test": "test"})
		self.queue.enqueue({"test2": "test2"})
		assert self.queue.len() == 2
		assert self.queue.dequeue() == {"test": "test"}
		assert self.queue.dequeue() == {"test2": "test2"}



