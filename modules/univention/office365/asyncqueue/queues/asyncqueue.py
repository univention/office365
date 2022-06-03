import glob
import json
import logging
import os.path
import pickle
import shutil
import tempfile
import time
import abc
from abc import abstractmethod
import six

from typing import Any


@six.add_metaclass(abc.ABCMeta)
class AbstractQueue(object):
	def __init__(self, queue_name):
		# type: (str) -> None
		self.name = queue_name

	@abstractmethod
	def enqueue(self, item):
		# type: (Any) -> None
		raise NotImplementedError()

	@abstractmethod
	def dequeue(self):
		# type: () -> Any
		raise NotImplementedError()

	@abstractmethod
	def __len__(self):
		# type: () -> int
		raise NotImplementedError()

	@abstractmethod
	def clear(self):
		# type: () -> None
		raise NotImplementedError()




