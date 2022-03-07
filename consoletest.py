#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Univention Office 365 - cmdline tests
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

from __future__ import print_function

import argparse
import sys
import pprint
import random
import base64

from univention.config_registry import ConfigRegistry
from univention.office365.azure_handler import AzureHandler
from univention.office365.azure_auth import AzureADConnectionHandler

EXAMPLES = """\
ADD USERS | GROUPS
------------------
{0} add users

ADD USERS or GROUPS TO A GROUP
------------------------------
{0} -o <objID of target group> add groups <objID of a user or group>  # adding multiple is broken

LIST USERS | GROUPS | DOMAINS | SUBSCRIPTIONS | ADCONNECTION
------------------------------------------------------
{0} list users
{0} list users -s
{0} list users -c
{0} list users -f 'accountEnabled eq true'
{0} list users -s -f "startswith(displayName,'John')"
{0} list users -s -f "accountEnabled eq true and startswith(displayName,'John')"
{0} list groups -f "displayName eq 'testgroup01'"
{0} list domains
{0} list subscriptions
{0} list adconnection

MODIFY USERS | GROUPS
---------------------
{0} -o bd5ea47e-cc70-4c5e-9c66-b6a07695b7d1 modify users 'displayName=John Doe' 'country=DE' 'accountEnabled=false'
{0} -o a8fcc4d7-40ca-4648-9593-536e9d73ea77 modify groups "displayName=group9033" "mailNickname=group9033"

DELETE USERS | GROUPS
---------------------
{0} -o bd5ea47e-cc70-4c5e-9c66-b6a07695b7d1 delete users

MEMBEROF USERS
--------------
{0} -o bd5ea47e-cc70-4c5e-9c66-b6a07695b7d1 memberofgroups users
{0} -o bd5ea47e-cc70-4c5e-9c66-b6a07695b7d1 memberofobjects users

LICENSES
--------
{0} -o bd5ea47e-cc70-4c5e-9c66-b6a07695b7d1 modify licenses add=189a915c-fe4f-4ffa-bde4-85b9628d07a0
{0} -o bd5ea47e-cc70-4c5e-9c66-b6a07695b7d1 modify licenses remove=189a915c-fe4f-4ffa-bde4-85b9628d07a0
""".format(sys.argv[0])


def print_users(users, complete=False, short=False):
	if not users:
		print("None.")
		return
	if users["odata.metadata"].endswith("@Element"):
		users = [users]
	else:
		users = users["value"]
	for user in users:
		print(u"objectType: {0} objectId: {1} accountEnabled: {2} displayName: '{3}'".format(
			user["objectType"],
			user["objectId"],
			user["accountEnabled"],
			user["displayName"]))
		if short:
			pass
		elif complete:
			pprint.pprint(user)
			print("")
		else:
			for attr in ["accountEnabled", "displayName", "mail", "odata.type", "otherMails", "userPrincipalName"]:
				if attr in user:
					print(u"      {0}: {1}".format(attr, user[attr]))
				else:
					print("      no attr {0}".format(attr))
			print("      assignedPlans:")
			for plan in user["assignedPlans"]:
				print(u"            service: {0} \t capabilityStatus: {1}".format(
					plan["service"],
					plan["capabilityStatus"]))
			if not user["assignedPlans"]:
				print("            None")
			print("      provisionedPlans:")
			for plan in user["provisionedPlans"]:
				print(u"            service: {0} \t capabilityStatus: {1} \t provisioningStatus: {2}".format(
					plan["service"], plan["capabilityStatus"], plan["provisioningStatus"]))
			if not user["provisionedPlans"]:
				print("            None")


def print_groups(groups, complete=False, short=False):
	if not groups:
		print("None.")
		return

	if groups["odata.metadata"].endswith("@Element"):
		groups = [groups]
	else:
		groups = groups["value"]
	for group in groups:
		try:
			print(u"objectType: {0} objectId: {1} displayName: '{2}'".format(group["objectType"], group["objectId"], group["displayName"]))
			if short:
				pass
			else:
				pprint.pprint(group)
				print("")
		except KeyError:
			print("type(groups): {}".format(type(groups)))
			pprint.pprint(group)
			print("")


def member_of(action, objectid):
	if action == "groups":
		return ah.member_of_groups(objectid)
	else:
		return ah.member_of_objects(objectid)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Test what we can currently do...")
	parser.add_argument("-c", "--complete", help="if action is 'list', show all attributes of objects [default off]", action="store_true")
	parser.add_argument("-f", "--filter", help="if action is 'list', retrieve only those objects that match FILTER, eg \"startswith(displayName,'test')\"")
	parser.add_argument("-o", "--objectid", help="if action is 'list', 'modify', 'delete' or 'memberof', set the object ID [required with 'modify', 'delete', 'memberof'].")
	parser.add_argument("-s", "--short", help="if action is 'list', only list object IDs [default off]", action="store_true")
	parser.add_argument("-v", "--verbosity", help="once to send syslog output of level INFO to console, twice (-vv) for DEBUG output [default off]", action="count")
	parser.add_argument("connection", help="connection to use")
	parser.add_argument("action", help="add/list/modify/delete/memberofgroups/memberofobjects/examples")
	parser.add_argument("object", help="users/groups/licenses/domains/subscriptions")
	parser.add_argument("set", help="if action is 'add' (TODO) or 'modify', set attribute 'key' of object to 'value' [required only for 'modify'].", nargs="*", metavar="key=value")
	args = parser.parse_args()

	if args.short and args.complete:
		parser.error("-c (--complete) and -s (--short) are mutually exclusive.")
	if args.filter and not args.action == "list":
		parser.error("--filter is only allowed with the 'list' action.")
	if args.filter and args.objectid:
		parser.error("Combining --filter and --objectid is not currently supported by azure.")
	if args.action in ["modify", 'delete', 'memberof'] and not args.objectid:
		parser.error("An object ID (a string of form '893801ca-e843-49b7-9f64-7a4590b72769') must be supplied with the -o option.")
	if args.action == "modify" and not args.set:
		parser.error("Please supply the attributes and values to modify in the form key=value. Multiple arguments may be supplied and must be seprarated by spaces.")

	if args.verbosity is None:
		args.verbosity = 0

	if args.connection not in AzureADConnectionHandler.get_adconnection_aliases():
		parser.error("choose one of these connections: {}".format(AzureADConnectionHandler.get_adconnection_aliases()))

	if args.object in ["users", "groups", "licenses", "domains", "subscriptions", "adconnection"]:
		if args.action == "examples":
			print(EXAMPLES)
			sys.exit(0)
		elif args.action == "list":
			# see below
			pass
	else:
		parser.error(u"Unknown object '{0}'.".format(args.object))

	ucr = ConfigRegistry()
	ucr.load()
	ah = AzureHandler(ucr, args.connection, args.connection)

	if args.action == "add":
		if args.objectid:
			if args.set:
				ah.add_objects_to_azure_group(args.objectid, args.set)
			else:
				parser.error("Please supply the objectIDs of users or groups to add to the group.")
		else:
			name = "name{0}".format(random.randint(1000, 9999))
			print("adding {0} with random name '{1}'...".format(args.object, name))
			if args.object == "users":
				attributes = {
					"accountEnabled": True,
					"displayName": name,
					"mailNickname": name,
					"immutableId": base64.b64encode(str(random.randint(100000000, 999999999)).encode("ASCII")).decode("ASCII"),
					"passwordProfile": {
						"password": "univention.99",
						"forceChangePasswordNextLogin": False},
					"userPrincipalName": "{0}@{1}".format(name, ah.get_verified_domain_from_disk())}
				ah.create_user(attributes)
				new_user = ah.list_users(ofilter="userPrincipalName eq '{}'".format(attributes["userPrincipalName"]))
				print_users(new_user, args.complete, args.short)
			elif args.object == "groups":
				ah.create_group(name)
				new_group = ah.list_groups(ofilter="displayName eq '{}'".format(name))
				print_groups(new_group, args.complete, args.short)
			else:
				print("other object types not yet implemented")
	elif args.action == "list":
		print("listing {0}: {1}...".format(args.object, args.objectid if args.objectid else "all"))
		if args.object == "users":
			users = ah.list_users(args.objectid, args.filter)
			print_users(users, args.complete, args.short)
		elif args.object == "groups":
			groups = ah.list_groups(args.objectid, args.filter)
			print_groups(groups, args.complete, args.short)
			if groups["odata.metadata"].endswith("@Element"):
				groups = [groups]
			else:
				groups = groups["value"]
			for group_id in [g["objectId"] for g in groups]:
				print("MEMBERS OF %r:" % group_id)
				members = ah.get_groups_direct_members(group_id)
				if "value" in members:
					print("\n".join([m["url"] for m in members["value"]]) if members["value"] else "None.")
				else:
					print("Error retrieving group members.")
					print(members)
				print("")
		elif args.object == "subscriptions":
			subscriptions = ah.list_subscriptions()
			pprint.pprint(subscriptions)
		elif args.object == "domains":
			domains = ah.list_verified_domains()
			pprint.pprint(domains)
		elif args.object == "adconnection":
			adconnection = ah.list_adconnection_details()
			pprint.pprint(adconnection)
		else:
			print("object type '{}' not yet implemented".format(args.object))
	elif args.action == "modify":
		if args.object not in ["users", "groups", "licenses"]:
			parser.error('Currently only object types "users", "groups" and "licenses" supported.')
		modifications = dict()
		for kv in args.set:
			try:
				key, value = kv.split("=")
				modifications[key] = value
			except ValueError:
				parser.error(u"Argument '{0}' is not of form KEY=VALUE.".format(kv))
		print(u"modifying {}: {} attributes: {}...".format(args.object[:-1], args.objectid, modifications))
		if args.object == "users":
			ah.modify_user(args.objectid, modifications)
		elif args.object == "groups":
			ah.modify_group(args.objectid, modifications)
		elif args.object == "licenses":
			for k, v in modifications.items():
				if k == "add":
					ah.add_license(args.objectid, v)
				elif k == "remove":
					ah.remove_license(args.objectid, v)
				else:
					parser.error("Only 'add' and 'remove' are allowed for license modifications.")
		else:
			parser.error("Unsupported object. This shouldn't happen.")
	elif args.action == "delete":
		if args.object not in ["users", "groups"]:
			parser.error('Currently only object types "users" and "groups" supported.')
		print("deleting {} {}...".format(args.object[:-1], args.objectid))
		if args.object == "users":
			ah.delete_user(args.objectid)
		else:
			ah.delete_group(args.objectid)
	elif args.action in ["memberofgroups", "memberofobjects"]:
		print("querying {0} of {1}...".format(args.action[8:], args.objectid))
		member_in = member_of(args.action[8:], args.objectid)
		print("member_in: {}".format(pprint.pformat(member_in)))
		print("{0} is member of the following {1}:".format(args.objectid, args.action[8:]))
		print("{}".format(member_in["value"]))
		if member_in["value"]:
			print("resolving object IDs...")
			objects = ah.resolve_object_ids(member_in["value"])
			print("objects: {}".format(pprint.pformat(objects)))
			for obj in objects["value"]:
				print("objectId {}:".format(obj["objectId"]))
				pprint.pprint(obj)

	else:
		parser.error(u"Unknown action '{0}'.".format(args.action))
	sys.exit(0)
