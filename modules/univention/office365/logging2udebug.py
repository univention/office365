#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - python logging to univention debug
# bridge (uses syslog if not running on UCS)
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

#
# Usage:
# logger = get_logger(logger_name, short_name, udebug_facility)
#
# logger_name: the name of the logger (see python logging)
# short_name: a string that will be prepended to all messages
# udebug_facility: the facility to log to with univention debug, defaults
#   to ud.LISTENER
#
# Then use it like a normal Python logging object (logger.debug() etc).
# Messages will go to the appropriate univention debug facility if running
# on UCS or syslog.LOG_USER otherwise (usually /var/log/user.log).
#
# When using with a listener, but testing from a python console nothing will
# be logged to listener.log. Add a handler in that situation:
# from logging.handlers import SysLogHandler
# <your module>.logger.addHandler(SysLogHandler(address="/dev/log"))
# Then you'll get a copy of all messages in /var/log/debug.
#

import logging
from six import PY2, PY3

import univention.debug as ud
from univention.config_registry import ConfigRegistry


LOG_FORMATS = dict(
	DEBUG="%(module)s.%(funcName)s:%(lineno)d  %(message)s",
	INFO="%(message)s"
)
for lvl in ["CRITICAL", "ERROR", "WARN", "WARNING"]:
	LOG_FORMATS[lvl] = LOG_FORMATS["INFO"]
LOG_FORMATS["NOTSET"] = LOG_FORMATS["DEBUG"]

LOGGING_TO_UDEBUG = dict(
	CRITICAL=ud.ERROR,
	ERROR=ud.ERROR,
	WARN=ud.WARN,
	WARNING=ud.WARN,
	INFO=ud.PROCESS,
	DEBUG=ud.ALL,
	NOTSET=ud.ALL
)

ucr = ConfigRegistry()
ucr.load()
_werror = ucr.is_true("office365/debug/werror", False)


def get_logger(logger_name, short_name=None, udebug_facility=ud.LISTENER):
	logger = logging.getLogger(logger_name)
	if not any(map(lambda x: isinstance(x, UDebugHandler), logger.handlers)):
		handler = UDebugHandler(udebug_facility=udebug_facility)
		handler.set_name(short_name or logger_name)
		handler.setFormatter(LevelDependentFormatter())
		handler.setLevel(logging.DEBUG)
		logger.addHandler(handler)
		logger.setLevel(logging.DEBUG)
	return logger


class LevelDependentFormatter(logging.Formatter):
	def format(self, record):
		if _werror:
			self._fmt = LOG_FORMATS["DEBUG"]
		else:
			self._fmt = LOG_FORMATS[record.levelname]
		if isinstance(record.args, dict) and "password" in record.args:
			record.args["password"] = "xxxxxxxxxx"
		elif hasattr(record.args, "__iter__"):
			for arg in record.args:
				if isinstance(arg, dict) and "password" in arg:
					arg["password"] = "xxxxxxxxxx"
		return super(LevelDependentFormatter, self).format(record)


class UDebugHandler(logging.Handler):
	def __init__(self, level=logging.NOTSET, udebug_facility=ud.LISTENER):
		self._udebug_facility = udebug_facility
		super(UDebugHandler, self).__init__(level)

	def emit(self, record):
		msg = self.format(record)
		if PY2 and isinstance(msg, unicode):
			msg = msg.encode("utf-8")
		elif PY3 and isinstance(msg, bytes):
			msg = msg.decode("utf-8", "replace")

		if _werror:
			udebug_level = ud.ERROR
			true_lvl = "({})".format(record.levelname[0])
		else:
			udebug_level = LOGGING_TO_UDEBUG[record.levelname]
			true_lvl = ""

		ud.debug(self._udebug_facility, udebug_level, "{}{}: {}".format(self.get_name(), true_lvl, msg))
