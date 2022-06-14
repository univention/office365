# -*- coding: utf-8 -*-
#
# Univention Office 365 - azuretask
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


from typing import Union, List, Dict, Tuple, Optional

import requests
import retrying
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.asyncqueue.tasks.task import Task
from logging import Logger

from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError


class MSGraphCoreTask(Task):
	def __init__(self, ad_connection_alias, method_name, method_args, sub_tasks=None):
		# type: (str, str, Union[List, Dict, Tuple], List["MSGraphCoreTask"]) -> None
		super(MSGraphCoreTask, self).__init__(sub_tasks)
		self.ad_connection_alias = ad_connection_alias
		self.method_name = method_name
		self.method_args = method_args

	def __dict__(self):
		# type: () -> Dict[str, Union[str, MSGraphCoreTask]]
		return {"ad_connection_alias": self.ad_connection_alias, "method_name": self.method_name, "method_args": self.method_args, "sub_tasks": [x.__dict__() for x in self.sub_tasks]}

	def dump(self):
		# type: () -> Dict[str, Union[str, MSGraphCoreTask]]
		return self.__dict__()

	def verify(self):
		# type: () -> bool
		if not AzureAccount(self.ad_connection_alias).is_initialized():
			return False
		if not hasattr(MSGraphApiCore, self.method_name):
			return False
		return True

	@classmethod
	def from_dict(cls, data):
		# type: ( Dict[str, Union[str, MSGraphCoreTask]]) -> MSGraphCoreTask
		data["sub_tasks"] = [MSGraphCoreTask.from_dict(x) for x in data["sub_tasks"]]
		return cls(**data)

	@retrying.retry(wait_exponential_multiplier=3000, wait_exponential_max=15000, stop_max_attempt_number=10)
	def run(self):
		# type: () -> bool
		core = MSGraphApiCore(AzureAccount(self.ad_connection_alias))
		method = getattr(core, self.method_name)
		self.logger.info("Calling to alias = %s MSGraphApiCore.%s with %r", self.ad_connection_alias, self.method_name, self.method_args)
		try:
			if isinstance(self.method_args, dict):
				method(**self.method_args)
			elif isinstance(self.method_args, (tuple, list)):
				method(*self.method_args)
			else:
				return False
				# raise TypeError("No valid type %s for args of %s" % (type(self.method_args), self.method_name))
		except MSGraphError as e:
			if self.logger:
				self.logger.error("Error while procesing task %r:", self.dump())
				raise
			return False
		return True
