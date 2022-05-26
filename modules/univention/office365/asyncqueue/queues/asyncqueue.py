import glob
import json
import logging
import os.path
import pickle
import shutil
import tempfile
import time
from abc import ABC, abstractmethod

from typing import Any


class AbstractQueue(ABC):
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




