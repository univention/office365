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


def progress(component=None, message=None, percentage=None, errors=None, critical=None, finished=False, **kwargs):
	return dict(
		component=component,
		message=message,
		percentage=percentage,
		errors=errors or [],
		critical=critical,
		finished=finished,
		**kwargs
	)


class Instance(Base):

	def init(self):
		self.azure_response = None

	@simple_response
	def query(self):
		fqdn = '%s.%s' % (ucr.get('hostname'), ucr.get('domainname'))
		return {
			'initialized': AzureAuth.is_initialized(),
			'login-url': '{origin}/univention-management-console/command/office365/authorize',
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

	@sanitize(
		id_token=StringSanitizer(),
		code=StringSanitizer(),
		session_state=StringSanitizer(),
		admin_consent=BooleanSanitizer(),
		error=StringSanitizer(),
		error_description=StringSanitizer()
	)
	def authorize(self, request):
		self.init()  # reset state in case the first attempt failed
		self.azure_response = {}
		self.azure_response.update(request.options)
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
			'content': _('The configuration has finished! You can now close this page and continue the configuration wizard.'),
		}
		self.finished(request.id, content, mimetype='text/html')

	@simple_response
	def state(self):
		options = self.azure_response
		if not options:
			return progress(message=_('Waiting for authorization to be completed.'), waiting=True)

		if options['id_token']:
			try:
				AzureAuth.parse_id_token(options['id_token'])
				AzureAuth.store_tokens(consent_given=True)
				aa = AzureAuth("office365")
				access_token = aa.retrieve_access_token()  # not really necessary, but it'll make sure everything worked
			except AzureError as exc:
				self.init()
				raise UMC_Error(str(exc))
			options['id_token'] = None
			return progress(message=_('Successfully authorized. Starting synchronization.'))
		elif options['error']:
			self.init()
			raise UMC_Error(_('Microsoft reported an error condition during authorization. It might help to reauthorize. Error message: {error}: {error_description}'.format(**options)))
		elif AzureAuth.is_initialized():
			self.init()
			try:
				ah = AzureHandler(ucr, "wizard")
				ah.list_users()
			#except TokenError as exc:
			#	return
			except AzureError as exc:
				raise UMC_Error(str(exc))

			try:
				subprocess.check_call(["invoke-rc.d", "univention-directory-listener", "crestart"])
			except (EnvironmentError, subprocess.CalledProcessError):
				pass
			return progress(message=_('Successfully initialized'), finished=True)
		return progress(message=_('Not yet initialized.'))
