# -*- coding: utf-8 -*-
#
# Univention Office 365 - login_exceptions
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


from typing import Optional


class GenericLoginException(Exception):
	def __init__(self, msg, chained_exc=None, adconnection_alias=None, *args, **kwargs):
		# type: (str, Optional[Exception], Optional[str], List, Dict) -> None
		self.chained_exc = chained_exc
		self.adconnection_alias = adconnection_alias
		super(GenericLoginException, self).__init__(msg, *args, **kwargs)  # TODO revisar


class TokenError(GenericLoginException):
	def __init__(self, msg, response=None, *args, **kwargs):
		# type: (str, Optional[requests.Response], List, Dict) -> None
		self.response = response
		if response and hasattr(response, "json"):
			j = response.json
			if callable(response.json):  # requests version compatibility
				j = j()
			self.error_description = j["error_description"]
		super(TokenError, self).__init__(msg, *args, **kwargs)


class IDTokenError(GenericLoginException):
	pass


class TokenValidationError(GenericLoginException):
	pass


class NoIDsStored(GenericLoginException):
	pass


class ManifestError(GenericLoginException):
	pass


class WriteScriptError(GenericLoginException):
	pass


class ADConnectionIDError(GenericLoginException):
	pass
