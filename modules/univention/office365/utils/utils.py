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