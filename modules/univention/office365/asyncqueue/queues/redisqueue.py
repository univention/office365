import pickle

import redis

from univention.office365.asyncqueue.queues.asyncqueue import AbstractQueue


class RedisQueue(AbstractQueue):
	def __init__(self, queue_name, redis_client):
		super().__init__(queue_name)
		self.redis_client = redis_client or redis.Redis()

	def push(self, item):
		self.redis_client.rpush(self.name, pickle.dumps(item))

	def pop(self):
		return pickle.loads(self.redis_client.brpop(self.name))

	def len(self):
		return self.redis_client.llen(self.name)



class SimpleQueue(AbstractQueue):
	def __init__(self, queue_name, conn=None):
		self.conn = conn or redis.Redis()
		self.name = queue_name

	def clear(self):
		self.conn.delete(self.name)

	def len(self):
		return self.conn.llen(self.name)

	def enqueue(self, task):
		serialized_task = pickle.dumps(task, protocol=pickle.HIGHEST_PROTOCOL)
		self.conn.lpush(self.name, serialized_task)
		return task

	def dequeue(self, process_task=False):
		_, serialized_task = self.conn.brpop(self.name)
		task = pickle.loads(serialized_task)
		if process_task:
			task.process()
		return task

	def get_length(self):
		return self.conn.llen(self.name)
