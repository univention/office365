import glob
import json
import logging
import os
import shutil
import time

from typing import Optional, List, Any, Dict

from univention.office365.asyncqueue import ASYNC_DATA_DIR
from univention.office365.asyncqueue.queues.asyncqueue import AbstractQueue
from univention.office365.asyncqueue.tasks.task import Task


class JsonFilesQueue(AbstractQueue):
	def __init__(self, queue_name, path=ASYNC_DATA_DIR, no_delete=False, logger=None):
		# type: (str, str, bool, Optional["logging.Logger"]) -> None
		super(JsonFilesQueue, self).__init__(queue_name)
		self.path = path if path and os.path.exists(path) else os.path.join("/tmp", queue_name)
		self.failed_path = os.path.join(self.path, 'failed')
		self.no_delete = no_delete
		self.logger = logger or logging.getLogger(__name__)
		os.makedirs(self.path, exist_ok=True)
		os.makedirs(self.failed_path, exist_ok=True)

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

	def verify_job(self, job):
		# type: (str) -> bool
		try:
			dumped = json.load(open(job))
		except ValueError as err:
			self.logger.error('Job {}: failed to parse json {}'.format(job, err))
			self.delete_job(job)
			return False
		if not dumped.get('api_version'):
			self.logger.error('Job {}: mandatory attribute api_version missing'.format(job))
			self.delete_job(job)
			return False
		if dumped['api_version'] != 1:
			self.logger.error('Job {}: invalid api_version {}'.format(job, dumped['api_version']))
			self.delete_job(job)
			return False
		for attr in ['function_name', 'ad_connection_alias']:
			if not dumped.get(attr):
				self.logger.error('Job {}: mandatory attribute {} missing'.format(job, attr))
				self.delete_job(job)
				return False
		if not dumped['ad_connection_alias'] in self.initialized_adconnections:
			self.get_ad_connections()
			if not dumped['ad_connection_alias'] in self.initialized_adconnections:
				self.logger.error('Job {}: invalid connection alias {}'.format(job, dumped['ad_connection_alias']))
				self.delete_job(job)
				return False
		func = getattr(self.initialized_adconnections[dumped['ad_connection_alias']], dumped.get('function_name'), None)
		if not func:
			self.logger.error('Job {}: invalid function name {}'.format(job, dumped.get('function_name')))
			self.delete_job(job)
			return False
		return True
