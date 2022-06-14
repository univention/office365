# -*- coding: utf-8 -*-
#
# Univention Office 365 - asyncqueue
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




