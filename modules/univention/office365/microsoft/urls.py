import six.moves.urllib.parse as urlparse

#TODO: implement variable version not only v1.0
from univention.office365.logging2udebug import get_logger

# TODO: use urlparse.urlunsplit
from univention.office365.ucr_helper import UCRHelper


class URLs:
	"""
	Class to hold all the URLs for the API.
	"""
	__ms_loging = "https://login.microsoftonline.com/{directory_id}/oauth2/v2.0/token"
	__ms_graph = "https://graph.microsoft.com/v1.0/"
	__resource_url = "https://graph.microsoft.com"

	def __init__(self, base_url):
		self.base_url = base_url

	@classmethod
	@property
	def resource_url(cls):
		return cls.__resource_url

	@classmethod
	def proxies(cls, ucr=None, logger=None):
		logger = logger or get_logger("office365", "URLs")
		return {} # UCRHelper.get_http_proxies(logger)

	@classmethod
	def base(cls):
		return cls.__ms_graph

	@classmethod
	def me(cls):
		return cls.__ms_graph + "me"

	@classmethod
	def ms_login(cls, directory_id):
		return cls.__ms_loging.format(directory_id=directory_id)

	@classmethod
	def groups(cls, params=None, path=None):
		path = "/" + path if path else ""
		params = "?" + params if params else ""
		return cls.__ms_graph + "groups" + path + params

	@classmethod
	def users(cls, params=None, path=None):
		"""https://graph.microsoft.com/v1.0/users"""
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "users" + path + params

	@classmethod
	def teams(cls, params=None, path=None):
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "teams" + path + params

	@classmethod
	def invitations(cls, params=None):
		params = "?"+params if params else "/"
		"""https://graph.microsoft.com/v1.0/invitations"""
		return cls.__ms_graph + "invitations"+params

	@classmethod
	def directory_objects(cls, params=None, path=None):
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "directoryObjects" + path + params

	@classmethod
	def domains(cls, params=None, path=None):
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "domains" + path + params

	@classmethod
	def subscription(cls, params=None, path=None):
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "subscribedSkus" + path + params