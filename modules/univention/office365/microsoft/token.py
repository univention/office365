# -*- coding: utf-8 -*-
#
# Univention Office 365 - token
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


import grp
import json
import os
import pwd
import shutil
import datetime

import six
from six.moves import UserDict

from six import reraise
from typing import Dict, Any, Tuple

from univention.office365.microsoft.jsonstorage import JsonStorage
from univention.office365.logging2udebug import get_logger
from univention.office365.utils.utils import token_decode_b64

uid = pwd.getpwnam("listener").pw_uid
gid = grp.getgrnam("nogroup").gr_gid

logger = get_logger("office365", "o365")


class Token(UserDict):
	"""
	A class to store the token data and provide a method to save it to a file.
	"""
	def __init__(self, connection_alias, base_path=None, **kwargs):
		if six.PY2:
			UserDict.__init__(self, **kwargs)
		else:
			super(Token, self).__init__(**kwargs)
		self.connection_alias = connection_alias
		base_path = base_path or "/etc/univention-office365/"
		self._token_cache = os.path.join(base_path, "{alias}/token.json".format(alias=connection_alias))
		if "nonce" in kwargs:
			JsonStorage(self._token_cache).write(**kwargs)
		self.load_token_cache()

	def load_token_cache(self):
		# type:() -> None
		if os.path.exists(self._token_cache):
			self.update(JsonStorage(self._token_cache).read())
		else:
			raise FileNotFoundError("Token cache file not found: {file}".format(file=self._token_cache))

	def check_token(self):
		# type: () -> None
		if 'expires_on' not in self:
			return False
		expires_on = datetime.datetime.strptime(self['expires_on'], "%Y-%m-%dT%H:%M:%S")
		# newer python versions will simplify this with:
		# expires_on = datetime.fromisoformat(token['expires_on'])

		# write some information about the token in use into the log file
		logger.debug(
			'The access token for `{alias}` looks'
			' similar to: `{starts}-trimmed-{ends}`.'
			' It is valid until {expires_on}'.format(
				starts=self['access_token'][:10],
				ends=self['access_token'][-10:],
				alias=self.connection_alias,
				expires_on=expires_on
			)
		)

		return (datetime.datetime.now() < expires_on)

	def update_and_save(self, response):
		# type: (Dict[str,Any]) -> None
		# it would be nicer to use the Date field from the response.header
		# instead of datetime.now(), but the level of abstraction does not
		# easily allow to come by. We cheat a little and our result could be
		# inaccurate, but the error handling in _call_graph_api would retry
		# with a new token, if that ever happened.
		expires_on = datetime.datetime.now() + datetime.timedelta(
			seconds=response['expires_in']
		)

		# Note, that the Azure API has had a field with the same name
		# 'expires_on' in its result, whereas we calculate the value for it
		# here locally...
		response['expires_on'] = expires_on.strftime('%Y-%m-%dT%H:%M:%S')

		self.update(response)

		token_file_tmp = self._token_cache + ".tmp"

		JsonStorage(token_file_tmp).write(**response)
		# with open(token_file_tmp, 'w') as f:
		# 	f.write(json.dumps(response))
		# move the temporary file to the final destination
		shutil.move(token_file_tmp, self._token_cache)

	def store_tokens(self, **kwargs):
		# type: (Dict[str,Any]) -> None
		JsonStorage(self._token_cache).write(**kwargs)

	@staticmethod
	def parse(encoded_token):
		# type: (str) -> Tuple[Dict[str, str], Dict[str, str], str]
		# JWT tokens have 3 segments: header, body, signature.
		try:
			_header, _body, _signature = encoded_token.split(".")
			decoded_header = token_decode_b64(_header)
			decoded_body = token_decode_b64(_body)
			return json.loads(decoded_header), json.loads(decoded_body), _signature
		except (AttributeError, TypeError, ValueError) as exc:
			et = encoded_token
			if isinstance(et, bytes):  # Python 2
				et = et.decode('UTF-8')
			logger.exception(u"Invalid token value: %r", et)
			reraise("""IDTokenError, IDTokenError(_("Error reading token of Azure AD connection {adconnection} received from Azure. Please run the wizard again.").format(adconnection=adconnection_alias), chained_exc=exc, adconnection_alias=adconnection_alias), sys.exc_info()[2]""")  # TODO ??? exception
