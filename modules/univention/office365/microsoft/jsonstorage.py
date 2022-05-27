import grp
import json
import logging
import pwd
import os
from stat import S_IRUSR, S_IWUSR

from typing import Dict

from univention.office365.logging2udebug import get_logger

uid = pwd.getpwnam("listener").pw_uid
gid = grp.getgrnam("nogroup").gr_gid

class JsonStorage(object):

	def __init__(self, filename, logger=None):
		# type: (str, "logging.Logger") -> None
		self.logger = logger or get_logger("office365", "o365")
		self.filename = filename

	def read(self):
		# type: () -> Dict
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
		# type: (Dict) -> None
		data = self.read()
		data.update(kwargs)
		self._save(data)

	def purge(self):
		# type: () -> None
		self._save({})

	def _save(self, data):
		# type: (Dict) -> None
		open(self.filename, "w").close()  # touch
		# os.chmod(self.filename, S_IRUSR | S_IWUSR)
		# os.chown(self.filename, self.listener_uid, 0)
		os.chmod(self.filename, 0o700)
		os.chown(self.filename, uid, gid)
		with open(self.filename, "w") as fd:
			json.dump(data, fd)
