import glob
import json
import logging
import os.path
import pickle
import shutil
import tempfile
import time
from abc import ABC, abstractmethod


class AbstractQueue(ABC):
	def __init__(self, queue_name):
		self.name = queue_name

	@abstractmethod
	def enqueue(self, item):
		raise NotImplementedError()

	@abstractmethod
	def dequeue(self):
		raise NotImplementedError()

	@abstractmethod
	def __len__(self):
		raise NotImplementedError()

	@abstractmethod
	def clear(self):
		raise NotImplementedError()




