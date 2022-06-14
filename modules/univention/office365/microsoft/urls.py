# -*- coding: utf-8 -*-
#
# Univention Office 365 - urls
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


import six.moves.urllib.parse as urlparse

#TODO: implement variable version not only v1.0
from typing import Optional, Dict

from univention.office365.logging2udebug import get_logger

# TODO: use urlparse.urlunsplit
from univention.office365.ucr_helper import UCRHelper


class URLs(object):
	"""
	Class to hold all the URLs for the API.
	"""
	__ms_loging = "https://login.microsoftonline.com/{directory_id}/oauth2/v2.0/token"
	__ms_graph = "https://graph.microsoft.com/v1.0/"
	__resource_url = "https://graph.microsoft.com"

	def __init__(self, base_url):
		# type: (str) -> None
		self.base_url = base_url

	@classmethod
	def resource_url(cls):
		# type: () -> str
		return cls.__resource_url

	@classmethod
	def proxies(cls, logger=None):
		# type: (Optional["logging.Logger"]) -> Dict[str,str]
		logger = logger or get_logger("office365", "URLs")
		return UCRHelper.get_http_proxies(logger)

	@classmethod
	def base(cls):
		# type: () -> str
		return cls.__ms_graph

	@classmethod
	def me(cls):
		# type: () -> str
		return cls.__ms_graph + "me"

	@classmethod
	def ms_login(cls, directory_id):
		# type: (str) -> str
		return cls.__ms_loging.format(directory_id=directory_id)

	@classmethod
	def groups(cls, params=None, path=None):
		# type: (Optional[str],Optional[str]) -> str
		path = "/" + path if path else ""
		params = "?" + params if params else ""
		return cls.__ms_graph + "groups" + path + params

	@classmethod
	def users(cls, params=None, path=None):
		# type: (Optional[str],Optional[str]) -> str
		"""https://graph.microsoft.com/v1.0/users"""
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "users" + path + params

	@classmethod
	def teams(cls, params=None, path=None):
		# type: (Optional[str],Optional[str]) -> str
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "teams" + path + params

	@classmethod
	def invitations(cls, params=None):
		# type: (Optional[str]) -> str
		params = "?"+params if params else "/"
		"""https://graph.microsoft.com/v1.0/invitations"""
		return cls.__ms_graph + "invitations"+params

	@classmethod
	def directory_objects(cls, params=None, path=None):
		# type: (Optional[str],Optional[str]) -> str
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "directoryObjects" + path + params

	@classmethod
	def domains(cls, params=None, path=None):
		# type: (Optional[str],Optional[str]) -> str
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "domains" + path + params

	@classmethod
	def subscription(cls, params=None, path=None):
		# type: (Optional[str],Optional[str]) -> str
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "subscribedSkus" + path + params

	@classmethod
	def service_principals(cls, params=None, path=None):
		# type: (Optional[str],Optional[str]) -> str
		path = "/" + path if path else ""
		params = "?"+params if params else ""
		return cls.__ms_graph + "servicePrincipals" + path + params