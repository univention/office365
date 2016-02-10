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

from univention.lib.i18n import Translation
from univention.management.console.base import Base
from univention.management.console.log import MODULE
from univention.management.console.config import ucr

from univention.management.console.modules.decorators import sanitize, simple_response, file_upload
from univention.management.console.modules.sanitizers import StringSanitizer

_ = Translation('univention-management-console-module-office365').translate


class Instance(Base):

	@simple_response
	def query(self):
		fqdn = '%s.%s' % (ucr.get('hostname'), ucr.get('domainname'))
		return {
			'initialized': True,#AzureAuth.is_initialized(),
			'login-url': 'https://%s/univention-office365/reply' % (fqdn,)
			'appid-url': 'https://%s/office365' % (fqdn,)
			'reply-url': 'https://%s/univention-office365/reply' % (fqdn,)
			'base-url': 'https://%s.%s/' % (fqdn,)
		}

	@file_upload
	def upload(self, request):
		self.finished(request.id, {
			'manifest': ''.encode('base64'),
			'authorizationurl': '/'  # AzureAuth.get_authorization_url(client_id),
		})

	@simple_response
	def test_configuration(self):
		return {
			'errors': [],
			'critical': False,
			'finished': True,
		}
