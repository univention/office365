import pickle

import redis
from typing import Optional, Any

from univention.office365.asyncqueue.queues.asyncqueue import AbstractQueue


class RedisQueue(AbstractQueue):
	def __init__(self, queue_name, redis_client):
		# type: (str, redis.Redis) -> None
		super().__init__(queue_name)
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
