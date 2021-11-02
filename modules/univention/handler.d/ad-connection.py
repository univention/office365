#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Copyright 2019-2021 Univention GmbH
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

from univention.admin.layout import Tab
import univention.admin.filter
import univention.admin.handlers
import univention.admin.syntax

translation = univention.admin.localization.translation('univention-admin-handlers-office365')
_ = translation.translate

module = 'office365/ad-connection'
childs = False
short_description = _(u'Microsoft 365 Azure AD Connection')
long_description = _(u'Management of Microsoft 365 Azure AD connections')
operations = ['add', 'edit', 'remove', 'search', 'move']
default_containers = ["cn=ad-connections,cn=office365"]

options = {
	'default': univention.admin.option(
		short_description='',
		objectClasses=['univentionOffice365ADConnection'],
	),
}

property_descriptions = {
	'name': univention.admin.property(
		short_description=_(u'Name'),
		long_description=_(u'Alias name of the connection.'),
		syntax=univention.admin.syntax.string,
		required=True,
		may_change=False,
		identifies=True,
	),
	'description': univention.admin.property(
		short_description=_(u'Description'),
		long_description='',
		syntax=univention.admin.syntax.string,
	),
}

layout = [
	Tab(_(u'General'), _(u'Microsoft 365 Azure AD Alias'), layout=[
		['name'],
		['description'],
	]),
]

mapping = univention.admin.mapping.mapping()
mapping.register('name', 'cn', None, univention.admin.mapping.ListToString)
mapping.register('description', 'description', None, None)


class object(univention.admin.handlers.simpleLdap):
	module = module


try:
	lookup = object.lookup
except AttributeError:
	# UCS < 4.2-2 errata206
	def lookup(co, lo, filter_s, base='', superordinate=None, scope='sub', unique=0, required=0, timeout=-1, sizelimit=0):
		searchfilter = univention.admin.filter.conjunction('&', [
			univention.admin.filter.expression('objectClass', 'univentionOffice365ADConnection'),
		])

		if filter_s:
			filter_p = univention.admin.filter.parse(filter_s)
			univention.admin.filter.walk(filter_p, univention.admin.mapping.mapRewrite, arg=mapping)
			searchfilter.expressions.append(filter_p)

		return [object(co, lo, None, dn, attr) for dn, attr in lo.search(unicode(searchfilter), base, scope, unique, required, timeout, sizelimit)]


try:
	identify = object.identify
except AttributeError:
	# UCS < 4.4-0-errata102
	def identify(distinguished_name, attributes, canonical=False):
		return 'univentionOffice365ADConnection' in attributes.get('objectClass', [])
