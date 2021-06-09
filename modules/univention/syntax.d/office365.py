# Office365 Azure AD Connection UDM syntax
#
# Copyright 2012-2019 Univention GmbH
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

import univention.admin.localization
from univention.admin.syntax import string, complex, UDM_Objects
import univention.admin.uexceptions


translation = univention.admin.localization.translation('univention-admin-handlers-office365')
_ = translation.translate

class Office365_User(UDM_Objects):
	udm_modules = ('users/user', )
	udm_filter = '(objectClass=univentionOffice365)'
	use_objects = False

class Office365_User(UDM_Objects):
	udm_modules = ('users/user', )
	# TODO mdb_equality_candidates: (univentionOffice365Enabled) not indexed
	udm_filter = '(&(objectClass=univentionOffice365)(univentionOffice365Enabled=1)(univentionOffice365Data=*))'
	use_objects = False


class univentionOffice365ProfileSyntax(UDM_Objects):
	empty_value = True
	udm_modules = ('office365/profile', )
	key = 'dn'
	label = '%(name)s'
	udm_filter = '(objectClass=univentionOffice365Profile)'
	simple = True
	regex = None


class univentionOffice365ADConnection(UDM_Objects):
	empty_value = True
	udm_modules = ('office365/ad-connection', )
	key = '%(name)s'
	label = '%(name)s'
	udm_filter = '(objectClass=univentionOffice365ADConnection)'
	simple = True
	regex = None


class univentionOffice365ADConnections(complex):
	"""
	Syntax for Azure AD connections

	>>> univentionOffice365ADConnections.parse(('defaultADconnection', 'dom1.user1@office365.dev-univention.de'))
	['defaultADconnection', 'dom1.user1@office365.dev-univention.de']
	"""
	subsyntaxes = (
		(_('Azure AD connection'), univentionOffice365ADConnection),
		(_('User Principal Name'), string),
	)
	subsyntax_names = ('AADConnection', 'userPrincipalName')
	all_required = True
