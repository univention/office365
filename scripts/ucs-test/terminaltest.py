#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Univention Microsoft 365 - cmdline microsoft graph tests
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

import os
import sys
import logging
import inspect
import json
import argparse

from argparse import RawTextHelpFormatter

from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError


def get_all_aliases():
	'''
		finds all aliases even if they are not in the univention config
		registry or initizlized.
	'''

	alias_path = '/etc/univention-office365'
	return [o for o in os.listdir(alias_path) if os.path.isdir(os.path.join(alias_path, o))]


def try_to_prettyprint(msg, indent=8):
	try:  # try to pretty print JSON from a string
		print(
			json.dumps(
				json.loads(msg),
				indent=indent,
				sort_keys=False
			)
		)
	except TypeError:  # maybe this is not a string, but already JSON?
		try:
			print(
				json.dumps(
					msg,
					indent=indent,
					sort_keys=False
				)
			)
		except ValueError:  # print as plain text otherwise
			print(msg)


if __name__ == "__main__":
	''' short 'flags' are hard coded while long opts are used to call functions
	and are dynamically derived from the class. Additions to the class
	automatically advance the amount of options this program offers.  '''

	# load the univention config registry, used to acquire some default values
	parser = argparse.ArgumentParser(
		description=(
			"Test for the Microsoft Graph API library integration"
		),
		epilog=(
			"Usage examples:"
			"\n\t{program} -g {alias}\t\t\t\t"
			"  \t# requests only a new access token"
			"\n\t{program} -g {alias} --function [argument(s)]"
			"  \t# requests access token and calls the function"
		).format(
			program=sys.argv[0],
			alias=get_all_aliases()[0]
		),
		formatter_class=RawTextHelpFormatter  # required for \n in epilog
	)

	parser.add_argument(
		"-g",
		choices=get_all_aliases(),
		help="test Microsoft graph library calls against this `alias` (required)",
		default=(get_all_aliases()[0])
	)

	parser.add_argument(
		'-a',
		action="store_true",
		help=inspect.cleandoc(get_all_aliases.__doc__ or "")
	)

	parser.add_argument(
		'-d',
		type=str.upper,  # ignore case, so that 'error' as well as 'ERROR' work
		default="ERROR",
		choices=[
			logging.getLevelName(n)
			for n in range(logging.NOTSET, logging.CRITICAL + 10, 10)
		], help="set the debug level for the logger."
	)

	# Now add all functions from the Graph class to this test program. If help
	# texts for functions are missing it is, because the functions do not have
	# a proper python docstring. Nothing needs to be hard-coded here any more.
	all_methods = filter(lambda x: not x[0].startswith('_'), [
		m for m in inspect.getmembers(MSGraphApiCore, predicate=inspect.ismethod)])

	for f in all_methods:
		arg_count = f[1].func_code.co_argcount - 1
		arguments = f[1].func_code.co_varnames[1:arg_count + 1]

		try:
			if arg_count == 0:  # only 'self'
				parser.add_argument(
					'--' + f[0],
					help=inspect.cleandoc(f[1].__doc__ or ""),
					action="store_true"
				)
			else:  # a method with parameters
				defaults = []
				help_defaults = ", defaults to: " + str(list(f[1].__defaults__ or []))
				parser.add_argument(
					'--' + f[0],
					help=inspect.cleandoc(f[1].__doc__ or "") + help_defaults,
					nargs=arg_count,
					metavar=arguments
				)
		except Exception as e:
			print(
				"Method parser failed for function '{function}{arguments}'"
				" with {argcount} arguments: {error}".format(
					error=str(e),
					function=f[0],
					arguments=arguments,
					argcount=arg_count
				))
			continue

	try:
		args = parser.parse_args()  # do not delete this line accidentally!
	except Exception as e:
		print("Error of type {type}: {error}".format(error=str(e), type=type(e)))

	if 1 == len(sys.argv):
		# Special case: Program was called without an argument. We assume, that
		# the person using it has forgotten how to use it and show this quick
		# intro.
		print(
			"Use `%s -a` to list all available pre-configured connections, also known as"
			" `connection-aliases` and usually configured via `/etc/univention-office365/`." % sys.argv[0]
		)
		print("")
		print(
			"Call this program with `%s -g <connection>` to use a specific connection."
			" Without further arguments that is enough to test which connection works"
			" and which does not and it gives hints why it does not." % sys.argv[0]
		)
		print("")
		print("If `-g` is skipped this program defaults to: `%s`." % args.g)
		print("")
		print("Use `%s --help` to list all functions which can be called using the connection." % sys.argv[0])

	elif args.a:
		print(json.dumps(get_all_aliases(), indent=4, sort_keys=True))

	elif args.g:
		logging.basicConfig(stream=sys.stderr, level=args.d)

		logger = logging.getLogger(__file__)
		logger.setLevel(getattr(logging, args.d.upper()))

		g = MSGraphApiCore(AzureAccount(args.g))  # the instantiation of the class requests a new access token

		arguments = [
			k for k, v in vars(args).iteritems()
			if v not in [None, False] and len(k) > 1
		]  # iterates over all arguments and skips flags with the length of 1

		# Note, that this implementation does not respect default values, which the
		# API functions may have. Instead all parameters must be specified
		# explicitly. There is no need for that now, but this might become
		# interesting in future in order to test default values.
		for arg in arguments:

			a = getattr(args, arg)

			# if (getattr(args, arg) is not None):
			# 	a = filter(lambda x: x is not '', getattr(args, arg))
			# 	if len(a) == 0:
			# 		a = True
			# assert(a is not None)

			f = getattr(g, arg)
			assert(callable(f))  # we assume, that the function is callable.

			# check if function has parameters or not
			try:
				if (isinstance(a, bool)):
					logger.info("@ executing: {method}(void)".format(method=arg))
					try_to_prettyprint(f())  # call a function without parameters
				else:  # means here: hasattr(a, '__iter__'), because a is a list
					logger.info("@ executing: {method}({params})".format(method=arg, params=a))
					try_to_prettyprint(f(*a))  # call a function with parameters

				logger.info("@ finished: {method}()".format(method=arg))
			except MSGraphError as e:
				logger.exception(e)
				# logger.exception(" {type} In '{method}': {error}".format(
				# 	type=type(e).__name__,
				# 	method=arg,
				# 	error=str(e))
				# )
	else:
		parser.print_help()

# vim: filetype=python noexpandtab tabstop=4 shiftwidth=4 softtabstop=4
