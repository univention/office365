import concurrent
import multiprocessing
from abc import abstractmethod, ABC
import random

import requests
import retrying
from typing import List, Dict, Union

PROCESSES = multiprocessing.cpu_count() - 1

class Task(ABC):

	def __init__(self, sub_tasks=None):
		# type: (List[Task]) -> None
		self.sub_tasks = sub_tasks or []

	def process(self):
		# type: () -> bool
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
		# type: () -> bool
		raise NotImplementedError

	def __dict__(self):
		# type: () -> Dict[str, Union[str,Task]]
		raise NotImplementedError

	def from_dict(self, data):
		# type: (Dict[str, Union[str,Task]]) -> Task
		raise NotImplementedError

	@abstractmethod
	def run(self):
		# type: () -> bool
		""" Run the task """
