import time
import random

import redis

from univention.office365.asyncqueue.queues.jsonfilesqueue import JsonFilesQueue
from univention.office365.asyncqueue.tasks.azuretask import MSGraphCoreTask

if __name__ == "__main__":
	q = JsonFilesQueue("o365test")
	while True:
		subtask1 = MSGraphCoreTask("patata_domain", "the_method1", (1, 2, 3))
		subtask2 = MSGraphCoreTask("patata_domain", "the_method2", (1, 2, 3))
		main_task = MSGraphCoreTask("patata_domain", "the_method3", (1, 2, 3), [subtask1, subtask2])
		q.enqueue(main_task)
		print(len(q))
		time.sleep(random.randint(1, 10))
