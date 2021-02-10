#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Univention Microsoft 365 - cmdline microsoft graph tests
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

import argparse
import logging

import json
import sys
from argparse import RawTextHelpFormatter
from univention.config_registry import ConfigRegistry

from univention.office365.api.graph import Graph
from univention.office365.api.exceptions import GraphError
from univention.office365.api.graph_auth import get_all_aliases_from_ucr, get_all_available_endpoints

if __name__ == "__main__":
	# logging.basicConfig(level=logging.DEBUG)

	ucr = ConfigRegistry()
	ucr.load()

	parser = argparse.ArgumentParser(
		description="Test for the Microsoft Graph API library integration",
		epilog="Usage example:\n"
		"\t{program} -g azuretestdomain --me".format(program=sys.argv[0]),
		formatter_class=RawTextHelpFormatter
	)

	parser.add_argument(
		'-v',
		'--verbose',
		help="set the verbosity/debug level for the logger:"
		"\n{notset}\tNOTSET"
		"\n{error}\tERROR"
		"\n{warning}\tWARNING"
		"\n{info}\tINFO"
		"\n{debug}\tDEBUG".format(
			notset=logging.NOTSET,
			error=logging.ERROR,
			warning=logging.WARNING,
			info=logging.INFO,
			debug=logging.DEBUG
		),
		type=int,
		choices=[
			logging.NOTSET,
			logging.ERROR,
			logging.WARNING,
			logging.INFO,
			logging.DEBUG
		],
		default=logging.ERROR
	)

	parser.add_argument(
		"-g",
		"--graph",
		help="test microsoft graph library calls against this `alias` (required)",
		choices=get_all_aliases_from_ucr(ucr)
	)

	parser.add_argument(
		'-a',
		'--aliases',
		help="list all aliases",
		action="store_true"
	)

	parser.add_argument(
		'-e',
		'--endpoints',
		help="list all endpoints",
		action="store_true"
	)

	parser.add_argument(
		'--me',
		help='display `me` endpoint (very simple call, good for debugging'
		'authentication problems)',
		action="store_true"
	)

	parser.add_argument(
		'--create_invitation',
		help='create an invitation (a user object marked as `guest`)',
		nargs=2,
		metavar=('invitedUserEmailAddress', 'inviteRedirectUrl')
	)

	parser.add_argument(
		'--create_team',
		help='create a new team',
		nargs=2,
		metavar=('name', 'description')
	)

	parser.add_argument(
		'--list_team_members',
		help='list team members',
		nargs=1,
		metavar=('team_id')
	)

	args = parser.parse_args()

	if args.endpoints:
		print(json.dumps(get_all_available_endpoints(ucr), indent=4, sort_keys=True))
	elif args.aliases:
		print(json.dumps(get_all_aliases_from_ucr(ucr), indent=4, sort_keys=True))
	elif args.graph:
		g = Graph(
			ucr=ucr,
			name=str(__file__),
			connection_alias=args.graph,
			loglevel=args.debug)

		try:
			if args.me:
				print(json.dumps(g.get_me(), indent=4, sort_keys=True))

			if args.create_team:
				name = args.create_team[0]
				desc = args.create_team[1]
				print('creating team: {name} - {desc}'.format(name=name, desc=desc))
				g.create_team(name, desc)

			if args.create_invitation:
				mail = args.create_invitation[0]
				url = args.create_invitation[1]
				print('creating invitation for: {mail} - {url}'.format(mail=mail, url=url))
				g.create_invitation(mail, url)

			if args.list_team_members:
				team_id = args.list_team_members[0]
				print('listing team members of {team_id}'.format(team_id=team_id))
				g.list_team_members(team_id)

		except GraphError as e:
			print("!! Graph Error occured: {msg}".format(msg=str(e)))
		except Exception as e:
			print("!! Unexpected Error occured: {msg}".format(msg=str(e)))
	else:
		parser.print_help()

# vim: filetype=python noexpandtab tabstop=4 shiftwidth=4 softtabstop=4
