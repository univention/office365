import time

import redis

# from univention.office365.asyncqueue.redisqueue import SimpleQueue
from univention.office365.asyncqueue.queues.jsonfilesqueue import JsonFilesQueue
from univention.office365.asyncqueue.tasks.azuretask import MSGraphCoreTask


def worker():
	r = redis.Redis()
	queue = JsonFilesQueue("o365test")
	if len(queue) > 0:
		task = MSGraphCoreTask.from_dict(queue.dequeue())
		task.process()
	else:
		print("No tasks in the queue")


if __name__ == "__main__":
	while True:
		worker()
		print("Sleeping for 3 seconds")
		time.sleep(3)