import base64
import subprocess
import random
import string

from univention.office365.logging2udebug import get_logger

logger = get_logger("office365", "o365")


def create_random_pw():
	# type: () -> str
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


def listener_restart():
	# type: () -> None
	logger.info('Restarting univention-directory-listener service')
	subprocess.call(['systemctl', 'restart', 'univention-directory-listener'])


def token_decode_b64(base64data):
	# type: (bytes) -> str
	# base64 strings should have a length divisible by 4
	# If this one doesn't, add the '=' padding to fix it
	leftovers = len(base64data) % 4
	if leftovers == 2:
		base64data += '=='
	elif leftovers == 3:
		base64data += '='

	decoded = base64.b64decode(base64data)
	return decoded.decode('utf-8')


def jsonify(data, encoding):
	if isinstance(data, (list, tuple)):
		new_data = []
		for x in data:
			new_data.append(jsonify(x, encoding))
		return new_data
	elif isinstance(data, set):
		new_data = set()
		for x in data:
			new_data.add(jsonify(x, encoding))
		return new_data
	elif isinstance(data, dict):
		new_data = dict()
		for k, v in data.items():
			new_data[ jsonify(k, encoding)] = jsonify(v, encoding)
		return new_data
	elif isinstance(data, type(u"")):
		try:
			return data.encode(encoding)
		except UnicodeEncodeError as e:
			return data.encode("utf-8")
	else:
		return data