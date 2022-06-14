# -*- coding: utf-8 -*-
#
# Univention Office 365 - office365-wsgi
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


import textwrap

from typing import List, Any, Callable, Dict
from univention.lib.i18n import Translation
_ = Translation('univention-management-console-module-office365').translate

try:
	from html import escape
	from urllib.parse import parse_qs
except ImportError:  # Python 2
	from cgi import escape, parse_qs


def application(environ, start_response):
	# type: (Dict[str,Any], Callable) -> List[str]
	status = '200 OK'
	response_header = [('Content-type', 'text/html; charset=UTF-8')]
	start_response(status, response_header)
	try:
		request_body_size = int(environ.get('CONTENT_LENGTH', 0))
	except (ValueError):
		request_body_size = 0

	request_body = environ['wsgi.input'].read(request_body_size)
	request_body = parse_qs(request_body)

	content = textwrap.dedent(u"""\
	<!DOCTYPE html>
	<html>
		<head>
			<title>%(title)s</title>
		</head>
		<body>
			<form action="/univention/command/office365/authorize_internal" id="form_auth" method="post">
	""" % {'title': _('Microsoft 365 Configuration finished')})

	for name, value in request_body.items():
		content += u'\t<input type="hidden" name="%s" value="%s" />\n' % (escape(name.decode("utf-8")), escape(value[0].decode("ASCII")))

	content += textwrap.dedent(u"""\
				<button type="submit">...</button>
			</form>
			<script type="application/javascript">//<!--
				document.getElementById("form_auth").submit();
			//--></script>
		</body>
	</html>
	""")
	return [content.encode('UTF-8')]
