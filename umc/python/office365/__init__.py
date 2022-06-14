#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention Management Console
#  module: Office 365 setup wizard
#
# Copyright 2016-2021 Univention GmbH
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

from six.moves.urllib import parse
import functools
import subprocess
import textwrap

from univention.lib.i18n import Translation
from univention.config_registry import handler_set
from univention.management.console.config import ucr
from univention.management.console.base import Base
from univention.management.console.error import UMC_Error, UnprocessableEntity
from univention.management.console.modules.decorators import sanitize, simple_response, file_upload, allow_get_request
from univention.management.console.modules.sanitizers import StringSanitizer, DictSanitizer, BooleanSanitizer, ValidationError, MultiValidationError
from univention.management.console.log import MODULE

from univention.office365.microsoft.account import AzureAccount, SAML_SETUP_SCRIPT_PATH
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError
from univention.office365.microsoft.exceptions.login_exceptions import ManifestError, ADConnectionIDError, GenericLoginException
from univention.office365.microsoft.manifest import Manifest
from univention.office365.ucr_helper import UCRHelper

_ = Translation('univention-management-console-module-office365').translate


def sanitize_body(sanizer):  # TODO: move into UMC core
	def _decorator(function):
		@functools.wraps(function)
		def _decorated(self, request, *args, **kwargs):
			try:
				sanizer.sanitize('request.body', {'request.body': request.body})
			except MultiValidationError as exc:
				raise UnprocessableEntity(str(exc), exc.result())
			except ValidationError as exc:
				raise UnprocessableEntity(str(exc), {exc.name: str(exc)})
			return function(self, request, *args, **kwargs)
		return _decorated
	return _decorator


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
		self.adconnection_alias = UCRHelper.adconnection_wizard()
		self.fqdn = '%s.%s' % (ucr.get('hostname'), ucr.get('domainname'))
		MODULE.process('adconnection_alias={!r}'.format(self.adconnection_alias))

	@simple_response
	def query(self):
		account = AzureAccount(self.adconnection_alias)
		return {
			'initialized': account.is_initialized(),
			'login-url': '{origin}/microsoft365-authorize',
			'appid-url': 'https://%s/office365' % (self.fqdn,),
			'base-url': 'https://%s/' % (self.fqdn,),
		}

	@file_upload
	@sanitize(DictSanitizer(dict(
		tmpfile=StringSanitizer(required=True)
	), required=True))
	@sanitize_body(DictSanitizer(dict(
		domain=StringSanitizer(required=True, minimum=1),
		adconnection_id=StringSanitizer(default='common'),
	), required=True))
	def upload(self, request):
		account = AzureAccount(self.adconnection_alias)
		account.uninitialize()

		try:
			adconnection_id = request.body.get('adconnection_id') or 'common'
			adconnection_id = parse.urlparse(adconnection_id).path.strip('/').split('/')[0]
			with open(request.options[0]['tmpfile']) as fd:
				manifest = Manifest(fd, self.adconnection_alias, adconnection_id, request.body['domain'])
			manifest.transform()
		except ManifestError as exc:
			raise UMC_Error(str(exc))

		try:
			account.store_manifest(manifest)
		except ADConnectionIDError:
			raise UMC_Error(_("Invalid federation metadata document address (e.g. https://login.microsoftonline.com/3e7d9eb4-c4a1-4cfd-893e-a8ec29e46b77/federationmetadata/2007-06/federationmetadata.xml)."))
		except MSGraphError as exc:
			raise UMC_Error(str(exc))

		try:
			authorizationurl = account.get_authorization_url()
		except GenericLoginException as exc:
			raise UMC_Error(str(exc))

		self.finished(request.id, {
			'authorizationurl': authorizationurl,
		}, message=_('The manifest has been successfully uploaded.'))

	@allow_get_request
	def manifest_json(self, request):
		account = AzureAccount(self.adconnection_alias)
		with open(account.conf_dirs['MANIFEST_FILE'], 'rb') as fd:
			self.finished(request.id, fd.read(), mimetype='application/octet-stream')

	@allow_get_request
	def saml_setup_script(self, request):
		with open(SAML_SETUP_SCRIPT_PATH.format(adconnection_alias='_{}'.format(self.adconnection_alias) if self.adconnection_alias else ''), 'rb') as fd:
			self.finished(request.id, fd.read(), mimetype='application/octet-stream')

	@allow_get_request
	def public_signing_cert(self, request):
		account = AzureAccount(self.adconnection_alias)
		with open(account.conf_dirs['SSL_CERT'], 'rb') as fd:
			self.finished(request.id, fd.read(), mimetype='application/octet-stream')

	@allow_get_request
	@sanitize(
		id_token=StringSanitizer(),
		code=StringSanitizer(),
		session_state=StringSanitizer(),
		admin_consent=BooleanSanitizer(),
		error=StringSanitizer(),
		error_description=StringSanitizer()
	)
	def authorize_internal(self, request):
		self.init()  # reset state in case the first attempt failed
		self.azure_response = {}
		self.azure_response.update(request.options)
		content = textwrap.dedent(u"""\
		<!DOCTYPE html>
		<html>
			<head>
				<title>%(title)s</title>
					<script type="application/javascript">//<!--
						window.close();
						window.top.close();
					//--></script>
			</head>
			<body>
				%(content)s
				</body>
		</html>
		""" % {
			'title': _('Microsoft 365 Configuration finished'),
			'content': _('The configuration has finished! You can now close this page and continue the configuration wizard.'),
		})

		self.finished(request.id, content.encode('UTF-8'), mimetype='text/html')

	@simple_response
	def state(self):
		options = self.azure_response
		account = AzureAccount(self.adconnection_alias)
		if not options:
			return progress(message=_('Waiting for authorization to be completed.'), waiting=True)

		if options['id_token']:
			try:
				account.parse_id_token(options['id_token'])
				account.token.store_tokens(consent_given=True)

				account.write_saml_setup_script()
				UCRHelper.set_ucs_overview_link()
				core = MSGraphApiCore(account)
				core.get_token()  # not really necessary, but it'll make sure everything worked
			except MSGraphError as exc:
				self.init()
				raise UMC_Error(str(exc))
			options['id_token'] = None
			if self.adconnection_alias:
				ucrv_set = '{}{}={}'.format(
					UCRHelper.adconnection_alias_ucrv,
					self.adconnection_alias,
					account['adconnection_id']
				)
				MODULE.process('Setting UCR {}...'.format(ucrv_set))
				handler_set([ucrv_set])
			return progress(message=_('Successfully authorized. Starting synchronization.'))
		elif options['error']:
			self.init()
			raise UMC_Error(_('Microsoft reported an error condition during authorization. It might help to reauthorize. Error message: {error}: {error_description}').format(**options))
		elif account.is_initialized():
			self.init()
			try:
				core = MSGraphApiCore(account)
				users = core.list_users()
				MODULE.process('Retrieved list of users: %r' % users)

			#except TokenError as exc:
			#	return
			except MSGraphError as exc:
				raise UMC_Error(str(exc))

			try:
				subprocess.call(["systemctl", "restart", "univention-directory-listener.service"])
			except (EnvironmentError,):
				pass
			return progress(message=_('Successfully initialized'), finished=True)
		return progress(message=_('Not yet initialized.'))
