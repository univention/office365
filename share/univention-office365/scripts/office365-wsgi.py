# -*- coding: utf-8 -*-
#
# Univention Office 365 - office365-wsgi
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only


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
    except ValueError:
        request_body_size = 0

    request_body = environ['wsgi.input'].read(request_body_size)
    request_body = parse_qs(request_body)

    content = textwrap.dedent(
        """\
	<!DOCTYPE html>
	<html>
		<head>
			<title>%(title)s</title>
		</head>
		<body>
			<form action="/univention/command/office365/authorize_internal" id="form_auth" method="post">
	"""
        % {'title': _('Microsoft 365 Configuration finished')}
    )

    for name, value in request_body.items():
        content += '\t<input type="hidden" name="%s" value="%s" />\n' % (escape(name.decode('utf-8')), escape(value[0].decode('ASCII')))

    content += textwrap.dedent("""\
				<button type="submit">...</button>
			</form>
			<script type="application/javascript">//<!--
				document.getElementById("form_auth").submit();
			//--></script>
		</body>
	</html>
	""")
    return [content.encode('UTF-8')]
