# -*- coding: utf-8 -*-
#
# Univention Office 365 - WSGI script to receive authentication tokens
# from MS Azure
#
# Copyright 2015 Univention GmbH
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

from urlparse import parse_qs
import cgi
import pprint

from univention.office365.azure_auth import AzureAuth, log_a, log_ex, log_p


def _parse_GET(environ):
	try:
		get_data = parse_qs(environ["QUERY_STRING"])
		# [str] -> str
		for k, v in get_data.items():
				if type(v) == list and len(v) == 1:
					get_data[k] = v[0]
	except:
		log_ex("in _parse_GET()")
		get_data = dict()
	return get_data


def is_POST_request(environ):
	try:
		if environ['REQUEST_METHOD'].upper() != 'POST':
			return False
		content_type = environ.get('CONTENT_TYPE', 'application/x-www-form-urlencoded')
		return (content_type.startswith('application/x-www-form-urlencoded') or
			content_type.startswith('multipart/form-data'))
	except:
		log_ex("in is_POST_request()")


class InputProcessed(object):
	try:
		def read(self, *args):
			raise EOFError('The wsgi.input stream has already been consumed')
		readline = readlines = __iter__ = read
	except:
		log_ex("in InputProcessed()")


def get_POST_form(environ):
	try:
		assert is_POST_request(environ)
		input = environ['wsgi.input']
		post_form = environ.get('wsgi.post_form')
		if (post_form is not None and
				post_form[0] is input):
			return post_form[2]
		# This must be done to avoid a bug in cgi.FieldStorage
		environ.setdefault('QUERY_STRING', '')
		fs = cgi.FieldStorage(fp=input, environ=environ, keep_blank_values=1)
		new_input = InputProcessed()
		post_form = (new_input, input, fs)
		environ['wsgi.post_form'] = post_form
		environ['wsgi.input'] = new_input
		return fs
	except:
		log_ex("in get_POST_form()")


def application(environ, start_response):
	log_p("application() Start azure callback")

	get_data = _parse_GET(environ)
	log_a("GET: %r" % get_data)

	if is_POST_request(environ):
		post_data_dict = dict()
		post_data = get_POST_form(environ)
		for key in post_data.keys():
			value = post_data.getvalue(key)
			if type(value) == list and len(value) == 1:
				value = value[0]
			post_data_dict[key] = value
		log_a("application() post_data_dict: %r" % post_data_dict)

		# The ID token we requested is included as the "id_token" form field
		try:
			id_token = post_data_dict["id_token"]
		except KeyError:
			log_ex("application() ACCESS DENIED.")
			raise
		# Get an access token
		AzureAuth.parse_id_token(id_token)
		aa = AzureAuth(None, "office365")
		access_token = aa.retrieve_access_token()  # not really necessary, but it'll make sure everything worked
		error = "None"
	else:
		error = "ERROR: no POST request"
		access_token = "None"

	html = """<!DOCTYPE HTML>
<html lang="en-US">
	<head>
		<meta charset="UTF-8">
		<title>Welcome back</title>
	</head>
	<body>
		<h1>Welcome back</h1>
		<p>error: {error}</p>
		<p>Aquired token: <small>{access_token}</small></p>
		<p>/etc/univention-office365/ids.json: <small>{ids}</small></p>
		<p>/etc/univention-office365/token.json: <small>{tokens}</small></p>
		<p>Now go do something useful with those tokens... like... run <code>./consoletest.py -h</code> &#9786;</p>
		<p>Link back to the <a href="/univention-office365/wizard">wizard</a>.</p>
	</body>
</html>""".format(
		error=error,
		access_token=access_token,
		ids=AzureAuth.load_azure_ids(),
		tokens=pprint.pformat(AzureAuth.load_tokens()).replace("\n", "<br/>"))
	status = "200 OK"
	response_headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(html)))]
	start_response(status, response_headers)
	log_p("End azure callback")
	return [html.encode("utf-8")]
