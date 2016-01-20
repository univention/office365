#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - UMC wizard
#
# Copyright 2016 Univention GmbH
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

try:
	from urlparse import parse_qs
except ImportError:
	# py3
	from urllib.parse import parse_qs

from univention.office365.azure_auth import AzureAuth, REDIRECT_URI, SCOPE, log_ex, log_p

#
# Until it has retrieved the client ID, the wizard may only use static methods of the AzureAuth class.
#

HTML_HEAD = """<!DOCTYPE HTML>
<html lang="en-US">
	<head>
		<meta charset="UTF-8">
		<title>UMC wizard</title>
	</head>
	<body>"""
HTML_FOOTER = """	</body>
</html>"""
HTML_STEP1 = """		<h1>Step 1 - Register App</h1>
		<ul>
			<li>create Azure account that is connected to the users Office 365 account</li>
			<li>create and configure App in Azure:</li>
			<ul>
				<li>configure redirect_uri: <code>%(redirect_uri)s</code></li>
				<li>configure "Berechtigungen f&uuml;r andere Anwendungen" &#8594; "Windows Azure Active Directory": checkboxes on for:
				<ul>
					<li>all of: <code>%(scope)s</code></li>
				</ul>
				<li>Download the manifest file and pipe it through manifest.py to add the public key, fingerprint etc.</li>
			</ul>
			<li>retrieve data from user:</li>
			<ul>
				<li>client ID</li>
				<li>domain name    # TODO: retrieve this from azure (currently hardcoded)</li>
			</ul>
			<li>next step: get admin consent by appending to this URL <code>?client_id=client-ID</code></li>
		</ul>
"""
HTML_STEP2 = """		<h1>Step 2 - Get admin consent</h1>
		<ul>
			<li>Got from user: client_id = <code>%(client_id)s</code></li>
			<li>Got from user: domain name = <code>%(domain)s</code>  # TODO: retrieve this from azure (currently hardcoded)</li>
		</ul>

		<h1>Authenticate</h1>
		<p>Follow the link to <a href="%(authorization_url)s">authenticate with your Admin account.</a></p>
"""


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


def application(environ, start_response):
	def _response(status, html):
		response_headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(html)))]
		start_response(status, response_headers)
		return [html.encode("utf-8")]

	#
	# Step 1: get Azure account, install App in Azure, get the Apps client ID
	#
	try:
		client_id = _parse_GET(environ)["client_id"]
	except KeyError:
		html = HTML_STEP1 % {
			"redirect_uri": REDIRECT_URI,
			"scope": SCOPE}
		return _response("412 Precondition Failed", html)
	AzureAuth.store_azure_ids(client_id=client_id, tenant_id=None)

	#
	# Step 2: using the Apps client ID get the URL for the admin consent,
	#         user will from there be redirected back to REDIRECT_URI
	#
	sign_in_url = AzureAuth.get_authorization_url(client_id)
	log_p("application() sign_in_url: {}".format(sign_in_url))

	html = HTML_STEP2 % {
		"client_id": client_id,
		"redirect_uri": REDIRECT_URI,
		"scope": SCOPE,
		"authorization_url": sign_in_url,
		"domain": "univentiontest.onmicrosoft.com"  # TODO: may not be needed, or can be retrieved later
	}
	return _response("200 OK", html)
