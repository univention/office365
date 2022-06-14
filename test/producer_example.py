# -*- coding: utf-8 -*-
#
# Univention Office 365 - producer_example
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

import time
import random

import redis

from univention.office365.asyncqueue.queues.jsonfilesqueue import JsonFilesQueue
from univention.office365.asyncqueue.tasks.azuretask import MSGraphCoreTask

if __name__ == "__main__":
	q = JsonFilesQueue("o365test")
	while True:
		subtask1 = MSGraphCoreTask("patata_domain", "the_method1", (1, 2, 3))
		subtask2 = MSGraphCoreTask("patata_domain", "the_method2", (1, 2, 3))
		main_task = MSGraphCoreTask("patata_domain", "the_method3", (1, 2, 3), [subtask1, subtask2])
		q.enqueue(main_task)
		print(len(q))
		time.sleep(random.randint(1, 10))