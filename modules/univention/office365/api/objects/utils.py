import random
import string
from typing import Iterable


def create_random_pw():
	# have at least one char from each category in password
	# https://msdn.microsoft.com/en-us/library/azure/jj943764.aspx
	pw = list(random.choice(string.ascii_lowercase))
	pw.append(random.choice(string.ascii_uppercase))
	pw.append(random.choice(string.digits))
	pw.append(random.choice(u"@#$%^&*-_+=[]{}|\\:,.?/`~();"))
	pw.extend(random.choice(string.ascii_letters + string.digits + u"@#$%^&*-_+=[]{}|\\:,.?/`~();") for _ in range(12))
	random.shuffle(pw)
	return u"".join(pw)


_default_azure_service_plan_names = "SHAREPOINTWAC, SHAREPOINTWAC_DEVELOPER, OFFICESUBSCRIPTION, OFFICEMOBILE_SUBSCRIPTION, SHAREPOINTWAC_EDU"


def get_service_plan_names(ucr):
	ucr_service_plan_names = ucr.get("office365/subscriptions/service_plan_names") or _default_azure_service_plan_names
	return [spn.strip() for spn in ucr_service_plan_names.split(",")]


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
