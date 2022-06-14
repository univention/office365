# -*- coding: utf-8 -*-
#
# Univention Office 365 - utils
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


from typing import Iterable, List, Union, Dict, Set


def remove_elements_from_containers(containers, elements):
	# type: (List[Union[List, Dict, Set]], Union[List, Dict, Set]) -> Union[List, Dict, Set]
	"""
	Remove elements from containers.
	The elements are removed from the containers in-place so the containers are modified after calling this function.
	"""
	assert isinstance(containers, Iterable), "container must be iterable"
	assert isinstance(elements, Iterable), "the_set must be a set"
	# convert dict, set or list to set
	elements = set(list(elements))
	for index, container in enumerate(containers):
		if isinstance(container, dict):
			containers[index] = {k: v for k, v in container.items() if k not in elements}
		elif isinstance(container, set):
			containers[index] = container - set(elements)
		elif isinstance(container, list):
			containers[index] = set([x for x in container if x not in elements])
	return containers
