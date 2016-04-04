#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Univention Management Console
#  module: Office 365 setup wizard
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

import json
import subprocess
import urlparse

from univention.lib.i18n import Translation
from univention.management.console.base import Base, UMC_Error
from univention.management.console.config import ucr

from univention.management.console.modules.decorators import sanitize, simple_response, file_upload
from univention.management.console.modules.sanitizers import StringSanitizer, DictSanitizer, BooleanSanitizer

from univention.office365.azure_auth import AzureAuth, AzureError, Manifest, ManifestError, TokenError
from univention.office365.azure_handler import AzureHandler

_ = Translation('univention-management-console-module-office365').translate


class Instance(Base):

	@simple_response
	def query(self):
		fqdn = '%s.%s' % (ucr.get('hostname'), ucr.get('domainname'))
		return {
			'initialized': AzureAuth.is_initialized(),
			'login-url': '{origin}/univention-management-console/command/office365/reply',
			'appid-url': 'https://%s/office365' % (fqdn,),
			'base-url': 'https://%s/' % (fqdn,),
		}

	@file_upload
	@sanitize(DictSanitizer(dict(
		tmpfile=StringSanitizer(required=True)
	), required=True))
	def upload(self, request):
		AzureAuth.uninitialize()

		try:
			with open(request.options[0]['tmpfile']) as fd:
				manifest = Manifest(fd)
			manifest.transform()
		except ManifestError as exc:
			raise UMC_Error(str(exc))

		try:
			tenant_id = request.body.get('tenant_id') or 'common'
			tenant_id = urlparse.urlparse(tenant_id).path.strip('/').split('/')[0]
			manifest.store(tenant_id)
		except AzureError as exc:
			raise UMC_Error(str(exc))

		try:
			authorizationurl = AzureAuth.get_authorization_url()
		except AzureError as exc:
			raise UMC_Error(str(exc))

		data = json.dumps(manifest.as_dict(), indent=2, separators=(',', ': '), sort_keys=True)
		self.finished(request.id, {
			'manifest': data.encode('base64'),
			'authorizationurl': authorizationurl,
		})

	@simple_response
	def test_configuration(self):
		finished = AzureAuth.is_initialized()
		errors = []
		if finished:
			try:
				ah = AzureHandler(ucr, "wizard")
				ah.list_users()
			except TokenError as exc:
				finished = False
				errors.append(str(exc))
			except AzureError as exc:
				errors.append(str(exc))
		if finished:
			try:
				subprocess.check_call(["invoke-rc.d", "univention-directory-listener", "crestart"])
			except (EnvironmentError, subprocess.CalledProcessError):
				pass
		return {
			'errors': errors,
			'critical': bool(errors),
			'finished': finished,
		}

	@sanitize(
		id_token=StringSanitizer(required=True),
		code=StringSanitizer(),
		session_state=StringSanitizer(),
		admin_consent=BooleanSanitizer()
	)
	def reply(self, request):
		try:
			AzureAuth.parse_id_token(request.options['id_token'])
			AzureAuth.store_tokens(consent_given=True)
			aa = AzureAuth("office365")
			access_token = aa.retrieve_access_token()  # not really necessary, but it'll make sure everything worked
		except AzureError as exc:
			raise UMC_Error(str(exc))
		content = """<!DOCTYPE html>
<html>
<head>
<title>%(title)s</title>
<script type="application/javascript">
window.close();
window.top.close();
</script>
</head>
<body>
%(content)s
</body>
</html>
		""" % {
			'title': _('Office 365 Configuration finished'),
			'content': _('The configuration was successful! You can now close this page and continue the configuration wizard.'),
		}
		self.finished(request.id, content, mimetype='text/html')
