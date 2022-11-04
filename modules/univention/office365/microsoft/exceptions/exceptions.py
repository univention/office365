# -*- coding: utf-8 -*-
#
# Univention Office 365 - exceptions
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


# MS Graph specific errors =====================================================

'''
	The GraphError class is kept very generic at this point. There will
	probably be more specific error messages required in the future and for
	that this file has already been prepared. That way we can keep the
	adaptions required to introduce new error types smaller.
'''


class NoAllocatableSubscriptions(Exception):
	def __init__(self, user, adconnection_alias=None, *args, **kwargs):
		# type: ("UserAzure", str, List, Dict) -> None
		self.user = user
		self.adconnection_alias = adconnection_alias
		super(NoAllocatableSubscriptions, self).__init__(*args, **kwargs)


class GraphError(Exception):
	pass


class GraphRessourceNotFroundError(GraphError):
	pass

# vim: filetype=python expandtab tabstop=4 shiftwidth=4 softtabstop=4
