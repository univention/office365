# -*- coding: utf-8 -*-
#
# Univention Office 365 - listener module
#
# Copyright 2015 Univention GmbH
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


__package__ = ''  # workaround for PEP 366

import os
import cPickle

import listener
from univention.office365.azure_handler import AzureHandler
from univention.office365.azure_auth import log_a, log_e, log_ex, log_p


name = 'office365'
description = 'manage office 365 user'
filter = '(&(objectClass=univentionOffice365)(uid=*))'
attributes = ['univentionOffice365Enabled']
modrdn = "1"

OFFICE365_OLD_PICKLE = os.path.join("/var/lib/univention-office365", "office365_old_dn")


class Office365Listener(AzureHandler):
	def __init__(self, listener, name):
		super(Office365Listener, self).__init__(listener, name)


def load_old(old):
	if os.path.exists(OFFICE365_OLD_PICKLE):
		f = open(OFFICE365_OLD_PICKLE, "r")
		p = cPickle.Unpickler(f)
		old = p.load()
		f.close()
		os.unlink(OFFICE365_OLD_PICKLE)
		return old
	else:
		return old


def save_old(old):
	f = open(OFFICE365_OLD_PICKLE, "w+")
	os.chmod(OFFICE365_OLD_PICKLE, 0600)
	p = cPickle.Pickler(f)
	p.dump(old)
	p.clear_memo()
	f.close()


def handler(dn, new, old, command):
	if command == 'r':
		save_old(old)
		return
	elif command == 'a':
		old = load_old(old)

	listener.configRegistry.load()
	ol = Office365Listener(listener, name)
	old_enabled = old.get("univentionOffice365Enabled", [""])[0].lower()
	new_enabled = new.get("univentionOffice365Enabled", [""])[0].lower()

	log_p("old_enabled: {}".format(old_enabled))
	log_p("new_enabled: {}".format(new_enabled))

	#
	# NEW account
	#
	if new and not old:
		log_p("new and not old -> NEW")
		return

	#
	# DELETE account
	#
	if old and not new:
		log_p("old and not new -> DELETE")
		return

	#
	# MODIFY account
	#
	if old and new:
		log_p("old and new -> MODIFY")
		return
