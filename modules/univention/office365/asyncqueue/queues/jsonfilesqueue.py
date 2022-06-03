import glob
import json
import logging
import os
import shutil
import time

from typing import Optional, List, Any, Dict

import six

from univention.office365.asyncqueue import ASYNC_DATA_DIR
from univention.office365.asyncqueue.queues.asyncqueue import AbstractQueue
from univention.office365.asyncqueue.tasks.task import Task
from univention.office365.utils.utils import jsonify


class JsonFilesQueue(AbstractQueue):
	def __init__(self, queue_name, path=ASYNC_DATA_DIR, no_delete=False, logger=None):
		# type: (str, str, bool, Optional["logging.Logger"]) -> None
		super(JsonFilesQueue, self).__init__(queue_name)
		self.path = path if path and os.path.exists(path) else os.path.join("/tmp", queue_name)
		self.failed_path = os.path.join(self.path, 'failed')
		self.no_delete = no_delete
		self.logger = logger or logging.getLogger(__name__)
		if not os.path.exists(self.path):
			os.makedirs(self.path)
		if not os.path.exists(self.failed_path):
			os.makedirs(self.failed_path)

	def enqueue(self, item, error=False):
		# type: (Task, bool) -> str
		path = self.path if not error else self.failed_path
		filename = os.path.join(path, '{time:f}.json'.format(time=time.time()))
		filename_tmp = filename + '.tmp'
		with open(filename_tmp, 'w') as fd:
			json.dump(item.__dict__(), fd, sort_keys=True, indent=4)
		shutil.move(filename_tmp, filename)
		if self.logger:
			self.logger.info('created async job {}'.format(filename))
		return filename

	def dequeue(self):
		# type: () -> Dict[str, Any]
		next_job = self.find_jobs()[0]
		with open(next_job, 'r') as f:
			json_data = json.load(f)
			if six.PY2:
				json_data = jsonify(json_data, "utf-8")
			self.delete_job(next_job)
			return json_data

	def __len__(self):
		# type: () -> int
		return len(self.find_jobs())

	def clear(self):
		# type: () -> None
		for file in self.find_jobs():
			self.delete_job(file)

	def find_jobs(self):
		# type: () -> List[str]
		return sorted(glob.glob(os.path.join(self.path, '*.json')))

	def find_job_by_name(self, name):
		# type: (str) -> Task
		""""""
		raise NotImplementedError

	def delete_job(self, job):
		# type: (str) -> None
		if not self.no_delete:
			if os.path.exists(job):
				self.logger.info('Job {}: removing'.format(job))
				os.remove(job)
