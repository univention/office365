#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: 2019-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

from six import text_type

from univention.admin.layout import Tab
import univention.admin.filter
import univention.admin.handlers
import univention.admin.syntax

translation = univention.admin.localization.translation('univention-admin-handlers-office365')
_ = translation.translate

module = 'office365/ad-connection'
childs = False
short_description = _('Microsoft 365 Azure AD Connection')
long_description = _('Management of Microsoft 365 Azure AD connections')
operations = ['add', 'edit', 'remove', 'search', 'move']
default_containers = ['cn=ad-connections,cn=office365']

options = {
    'default': univention.admin.option(
        short_description='',
        objectClasses=['univentionOffice365ADConnection'],
    ),
}

property_descriptions = {
    'name': univention.admin.property(
        short_description=_('Name'),
        long_description=_('Alias name of the connection.'),
        syntax=univention.admin.syntax.string,
        required=True,
        may_change=False,
        identifies=True,
    ),
    'description': univention.admin.property(
        short_description=_('Description'),
        long_description='',
        syntax=univention.admin.syntax.string,
    ),
}

layout = [
    Tab(
        _('General'),
        _('Microsoft 365 Azure AD Alias'),
        layout=[
            ['name'],
            ['description'],
        ],
    ),
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
        searchfilter = univention.admin.filter.conjunction(
            '&',
            [
                univention.admin.filter.expression('objectClass', 'univentionOffice365ADConnection'),
            ],
        )

        if filter_s:
            filter_p = univention.admin.filter.parse(filter_s)
            univention.admin.filter.walk(filter_p, univention.admin.mapping.mapRewrite, arg=mapping)
            searchfilter.expressions.append(filter_p)

        return [object(co, lo, None, dn, attr) for dn, attr in lo.search(text_type(searchfilter), base, scope, unique, required, timeout, sizelimit)]


try:
    identify = object.identify
except AttributeError:
    # UCS < 4.4-0-errata102
    def identify(distinguished_name, attributes, canonical=False):
        return 'univentionOffice365ADConnection' in attributes.get('objectClass', [])
