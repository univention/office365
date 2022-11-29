#!/usr/bin/python3
#
# -*- coding: utf-8 -*-
#
# Like what you see? Join us!
# https://www.univention.com/about-us/careers/vacancies/
#
# Copyright 2021-2022 Univention GmbH
#
# https://www.univention.de/
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
# <https://www.gnu.org/licenses/>.

import os
import pwd
import shutil
import subprocess
import pytest

from univention.config_registry import handler_set
import univention.testing.utils as utils

from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.account import AzureAccount
from univention.office365.connector.account_connector import AccountConnector

from helpers.office365_test_helpers import setup_logging


@pytest.fixture(scope='class')
def restart_listener_after_test():
	yield
	utils.restart_listener()


@pytest.fixture(scope='session')
def logger():
	return setup_logging()


@pytest.fixture(scope='session')
def adconnection_srcpath(request):
	return request.param


@pytest.fixture(scope='session')
def adconnection_alias(request):
	return request.param


@pytest.fixture(scope='session')
def core(adconnection_alias):
	return MSGraphApiCore(AzureAccount(adconnection_alias))
	# return MSGraphApiCore(adconnection)


@pytest.fixture(scope='session')
def adconnection(adconnection_alias, adconnection_srcpath):
	account = AzureAccount(adconnection_alias)
	assert account.is_initialized(), "run ./01_initialize_external_testenv first!"
	return account


@pytest.fixture(scope='session')
def initialize_adconnection(logger, adconnection_alias, adconnection_srcpath):
	"""
	This fixture configures the external connections for this connector instance.
	This fixture expects a preconfigured connection to Azure to be in /etc/univention-office365/

	Required arguments:
		- adconnection_alias: the alias with which the connection is initialized and used
		- adconnection_srcpath: the path to the artefacts of the preconfigured Azure connection

	Standard parameters are:
		("o365domain", "/etc/univention-office365/o365-dev-univention-de")
		("azuretestdomain", "/etc/univention-office365/u-azure-test-de")

	For initialization of the test environment, the content of these directories is copied from
	{adconnection_srcpath} to ...{adconnection_alias} and the UCRv
	office365/adconnection/alias/{adconnection_alias}=initialized set.
	"""
	# try:
	if not os.path.exists(f"/etc/univention-office365/{adconnection_alias}"):
		AccountConnector.create_new_adconnection(logger, adconnection_alias, restart_listener=False)
	account = AzureAccount(adconnection_alias)
	if not account.is_initialized():
		newconf_dir = account.conf_dirs.get("CONFDIR")
		srcpath = adconnection_srcpath
		shutil.rmtree(newconf_dir, ignore_errors=True)
		shutil.copytree(srcpath, newconf_dir)
		ucrv_set = f"office365/adconnection/alias/{adconnection_alias}=initialized"
		handler_set([ucrv_set])

	# TODO: Move the path to an external config file
	for root, dirs, files in os.walk("/etc/univention-office365"):
		for d in dirs:
			os.chown(os.path.join(root, d), pwd.getpwnam('listener').pw_uid, 0)
		for f in files:
			os.chown(os.path.join(root, f), pwd.getpwnam('listener').pw_uid, 0)
	subprocess.call(["service", "univention-directory-listener", "restart"])
	# except Exception:
	# 	import traceback
	# 	print(traceback.format_exc())
	# 	assert False, "Preparation of externally configured ad connections failed!"

	yield account

	account_connector = AccountConnector(logger)
	if account.is_initialized():
		account_connector.remove_adconnection("o365domain")
	return True
	# TODO: insert message if removal fails
	# assert remove_externally_configured_adconnections(logger), "Removgging of externally configured ad connections failed!"
