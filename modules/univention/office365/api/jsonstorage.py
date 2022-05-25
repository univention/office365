import json
import pwd
import os
from stat import S_IRUSR, S_IWUSR


class JsonStorage(object):
	listener_uid = None

	def __init__(self, filename, logger=None):
		self.logger = logger
		self.filename = filename
		if not self.listener_uid:
			self.__class__.listener_uid = pwd.getpwnam('listener').pw_uid

	def read(self):
		try:
			with open(self.filename, "r") as fd:
				data = json.load(fd)
		except (IOError, ValueError):
			data = dict()
		if not isinstance(data, dict):
			self.logger.error("AzureAuth._load_data(): Expected dict in file %r, got %r.", self.filename, data)
			data = dict()
		return data

	def write(self, **kwargs):
		data = self.read()
		data.update(kwargs)
		self._save(data)

	def purge(self):
		self._save({})

	def _save(self, data):
		open(self.filename, "w").close()  # touch
		os.chown(self.filename, self.listener_uid, 0)
		os.chmod(self.filename, S_IRUSR | S_IWUSR)
		with open(self.filename, "w") as fd:
			json.dump(data, fd)
