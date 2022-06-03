# -*- coding: utf-8 -*-
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
