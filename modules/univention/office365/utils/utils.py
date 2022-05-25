import base64
import subprocess

from univention.office365.logging2udebug import get_logger

logger = get_logger("office365", "o365")


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