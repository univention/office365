#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Copyright 2013-2016 Univention GmbH
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

from univention.admin.layout import Tab, Group
import univention.admin.filter
import univention.admin.handlers
import univention.admin.syntax

translation = univention.admin.localization.translation('office365')
_ = translation.translate

module = 'settings/office365profile'
childs = 0
short_description = _(u'Office 365 Profile')
long_description = _(u'Management of office 365 profiles')
operations = ['add', 'edit', 'remove', 'search', 'move']
default_containers=["cn=profiles,cn=office365"]

options = {}

property_descriptions = {
	'name': univention.admin.property(
		short_description = _(u'Profile name'),
		long_description = _(u'Displayed profile name when selecting a profile'),
		syntax = univention.admin.syntax.string,
		multivalue = False,
		required = True,
		may_change = True,
		identifies = False
	),
	'subscriptions': univention.admin.property(
		short_description=_(u'Subscription identifier'),
		long_description=_(u''),
		syntax=univention.admin.syntax.string,
		multivalue=0,
		required=1,
		may_change=1,
		identifies=0
	),
	'whitelisted_plans': univention.admin.property(
		short_description=_(u'Service plan whitelist'),
		long_description=_(u'Identifiers of service plans, which will be activated for the profile'),
		syntax=univention.admin.syntax.string,
		multivalue=1,
		required=0,
		may_change=1,
		identifies=0
	),
	'blacklisted_plans': univention.admin.property(
		short_description=_('Service plan blacklist'),
		long_description=_('Identifiers of service plans, which will be deactivated for the profile'),
		syntax=univention.admin.syntax.string,
		multivalue=1,
		required=0,
		may_change=1,
		identifies=0
	),
}

layout = [
	Tab(_(u'General'), _(u'Office 365 Profile'), layout=[
			[ 'name', ], [ 'subscription', ],
			[ 'service_plan_whitelist', ],
			[ 'service_plan_blacklist', ],
		]),
]

mapping = univention.admin.mapping.mapping()
mapping.register('name', 'office365ProfileName', None, univention.admin.mapping.ListToString)
mapping.register('subscription', 'office365ProfileSubscription', None, univention.admin.mapping.ListToString)
mapping.register('service_plan_whitelist', 'office365ProfileWhitelist', None, None)
mapping.register('service_plan_blacklist', 'office365ProfileBlacklist', None, None)

class object(univention.admin.handlers.simpleLdap):
	module = module

	def __init__(self, co, lo, position, dn='', superordinate=None, attributes=None):
		self.co = co
		self.lo = lo
		self.dn = dn
		self.position = position
		self.mapping = mapping
		self.descriptions = property_descriptions
		univention.admin.handlers.simpleLdap.__init__(self, co, lo, position, dn, superordinate)
		self.options = []

	def open(self):
		univention.admin.handlers.simpleLdap.open(self)
		self.save()

	def _ldap_pre_create(self):
		self.dn = '%s=%s,%s' % (mapping.mapName('name'), mapping.mapValue('name', self.info['name']), self.position.getDn())

	def _ldap_post_create(self):
		pass

	def _ldap_pre_modify(self):
		pass

	def _ldap_post_modify(self):
		pass

	def _ldap_pre_remove(self):
		pass

	def _ldap_post_remove(self):
		pass

	def _update_policies(self):
		pass

	def _ldap_addlist(self):
		return [('objectClass', ['top', 'univentionOffice365Profile',])]

def lookup(co, lo, filter_s, base='', superordinate=None, scope='sub', unique=0, required=0, timeout=-1, sizelimit=0):
	searchfilter = univention.admin.filter.conjunction('&', [
				univention.admin.filter.expression('objectClass', 'univentionOffice365Profile'),
				])

	if filter_s:
		filter_p = univention.admin.filter.parse(filter_s)
		univention.admin.filter.walk(filter_p, univention.admin.mapping.mapRewrite, arg=mapping)
		searchfilter.expressions.append(filter_p)

	res = []
	for dn in lo.searchDn(unicode(searchfilter), base, scope, unique, required, timeout, sizelimit):
		res.append(object(co, lo, None, dn))
	return res

def identify(distinguished_name, attributes, canonical=False):
	return 'univentionOffice365Profile' in attributes.get('objectClass', [])
