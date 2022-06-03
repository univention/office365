# -*- coding: utf-8 -*-
import concurrent
import multiprocessing
from abc import abstractmethod
import abc
import random

import requests
import retrying
from typing import List, Dict, Union
import six
PROCESSES = multiprocessing.cpu_count() - 1


@six.add_metaclass(abc.ABCMeta)
class Task(object):

	def __init__(self, sub_tasks=None):
		# type: (List[Task]) -> None
		self.sub_tasks = sub_tasks or []
		self.logger = None  # type: Optional[Logger]

	def set_logger(self, logger):
		# type: ("logging.Logger") -> None
		self.logger = logger

	def process(self):
		# type: () -> bool
		""" Process the task """
		if self.verify():
			self.logger.info('Gonna process {} sub tasks'.format(len(self.sub_tasks)))
			if self.sub_tasks:
				for task in self.sub_tasks:
					task.set_logger(self.logger)
					if not task.process():
						return False
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
