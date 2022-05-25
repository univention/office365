import concurrent
import multiprocessing
from abc import abstractmethod, ABC
import random

import requests
import retrying

PROCESSES = multiprocessing.cpu_count() - 1

class Task(ABC):

	def __init__(self, sub_tasks=None):
		self.sub_tasks = sub_tasks or []

	def process(self):
		""" Process the task """
		if self.verify():
			print('Gonna process {} sub tasks'.format(len(self.sub_tasks)))
			if self.sub_tasks:
				for task in self.sub_tasks:
					task.process()
			return self.run()
		else:
			return False

	def verify(self):
		raise NotImplementedError

	def __dict__(self):
		raise NotImplementedError

	def from_dict(self, data):
		raise NotImplementedError

	@abstractmethod
	def run(self):
		# type () -> bool
		""" Run the task """



#
# def execute_batch(batch_number):
# 	with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
# 		future_to_url = {executor.submit(load_url, url, PROCESSES): url for url in get_urls()}
# 		resp_ok = 0
# 		resp_err = 0
# 		for future in concurrent.futures.as_completed(future_to_url):
# 			url = future_to_url[future]
# 			try:
# 				data = future.result()
# 			except Exception as exc:
# 				resp_err = resp_err + 1
# 			else:
# 				resp_ok = resp_ok + 1
# 		print(f"Batch {batch_number} - OK: {resp_ok} - ERROR: {resp_err}")
# 		print(resp_ok, resp_err)
#
#
# def run():
# 	print(f"Running with {PROCESSES} processes!")
#
# 	start = time.time()
# 	with multiprocessing.Pool(PROCESSES) as p:
# 		p.map_async(
# 			execute_batch_with_retries,
# 			range(0, 10)
# 		)
# 		# clean up
# 		p.close()
# 		p.join()
#
# 	print(f"Time taken = {time.time() - start:.10f}")