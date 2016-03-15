#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - print directory data
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

from univention.office365.listener import Office365Listener
from univention.office365.azure_handler import ResourceNotFoundError

ol = Office365Listener({}, "print users and groups", {}, {}, "dn")
users = ol.ah.list_users()
groups = ol.ah.list_groups()

print("                  ID                 |           USER           | userPrincipalName")
print(92 * "-")
for user in users["value"]:
	try:
		name = user["displayName"]
		if name.startswith("ZZZ_deleted_"):
			name = "(DEL) {}".format(name[26:])
		print("%36s | %24s | %s" % (user["objectId"], name, user["userPrincipalName"][:52]))
	except KeyError:
		print(user)

print(92 * "=")
print("                  ID                 |           GROUP          | # members")
print(92 * "-")
member_ids = dict()
for group in groups["value"]:
	member_urls = ol.ah.get_groups_direct_members(group["objectId"])["value"]
	member_ids[group["displayName"]] = ol.ah.directory_object_urls_to_object_ids(member_urls)
	name = group["displayName"]
	if name.startswith("ZZZ_deleted_"):
		name = "(DEL) {}".format(name[26:])
	print("%36s | %24s | %d" % (group["objectId"], name, len(member_ids[group["displayName"]])))

print(92 * "=")
print("                GROUP                |          MEMBER")
print(92 * "-")
for name, member_ids in member_ids.items():
	for member_id in member_ids:
		try:
			member = ol.ah.list_users(objectid=member_id)
			membername = member["userPrincipalName"]
			if membername.startswith("ZZZ_deleted_"):
				membername = "(DEL) {}".format(membername[26:])
			print("%36s | user:  %s" % (name, membername))
		except ResourceNotFoundError:
			member = ol.ah.list_groups(objectid=member_id)
			membername = member["displayName"]
			if membername.startswith("ZZZ_deleted_"):
				membername = "(DEL) {}".format(membername[26:])
			print("%36s | group: %s" % (name, membername))
