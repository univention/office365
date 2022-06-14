# -*- coding: utf-8 -*-
#
# Univention Office 365 - task
#
# Copyright 2016-2022 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.


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
