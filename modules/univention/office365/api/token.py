import grp
import json
import os
import pwd
import shutil
import datetime
from collections import UserDict

from six import reraise
from typing import Dict, Any

from univention.office365.api.jsonstorage import JsonStorage
from univention.office365.logging2udebug import get_logger
from univention.office365.utils import token_decode_b64

uid = pwd.getpwnam("listener").pw_uid
gid = grp.getgrnam("nogroup").gr_gid

logger = get_logger("office365", "o365")

class TokenManager:
	def __init__(self, token_file):
		self.token_file = token_file
		self.token_data = {}
		self.load_token_data()

class Token(UserDict):
	"""
	A class to store the token data and provide a method to save it to a file.
	"""
	def __init__(self, connection_alias, base_path=None, **kwargs):
		super().__init__(**kwargs)
		self.connection_alias = connection_alias
		base_path = base_path or "/etc/univention-office365/"
		self._token_cache = os.path.join(base_path, "{alias}/token.json".format(alias=connection_alias))
		if "nonce" in kwargs:
			JsonStorage(self._token_cache).write(**kwargs)
		self.load_token_cache()

	def load_token_cache(self):
		if os.path.exists(self._token_cache):
			self.update(JsonStorage(self._token_cache).read())
		else:
			raise FileNotFoundError("Token cache file not found: {file}".format(file=self._token_cache))

	def check_token(self):
		if 'expires_on' not in self:
			return False
		expires_on = datetime.datetime.strptime(self['expires_on'], "%Y-%m-%dT%H:%M:%S")
		# newer python versions will simplify this with:
		# expires_on = datetime.fromisoformat(token['expires_on'])

		# write some information about the token in use into the log file
		logger.info(
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
		os.chmod(token_file_tmp, 0o700)
		os.chown(token_file_tmp, uid, gid)
		shutil.move(token_file_tmp, self._token_cache)

	def store_tokens(self, **kwargs):
		# type: (Dict[str,Any]) -> None
		JsonStorage(self._token_cache).write(**kwargs)

	@staticmethod
	def parse(encoded_token):
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
