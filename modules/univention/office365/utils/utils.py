import base64
import subprocess
import random
import string

from univention.office365.logging2udebug import get_logger

logger = get_logger("office365", "o365")


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


def listener_restart():
	logger.info('Restarting univention-directory-listener service')
	subprocess.call(['systemctl', 'restart', 'univention-directory-listener'])


def token_decode_b64(base64data):
	# base64 strings should have a length divisible by 4
	# If this one doesn't, add the '=' padding to fix it
	leftovers = len(base64data) % 4
	if leftovers == 2:
		base64data += '=='
	elif leftovers == 3:
		base64data += '='

	decoded = base64.b64decode(base64data)
	return decoded.decode('utf-8')