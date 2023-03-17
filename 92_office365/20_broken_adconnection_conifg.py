#!/usr/share/ucs-test/runner pytest-3 -s -l -vv
## -*- coding: utf-8 -*-
## desc: #TODO:
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365

import pytest
import shutil
import json
from pathlib import Path

from univention.office365.connector.connector import UserConnector
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError # , AddLicenseError, ItemNotFound, GraphPermissionError
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.logging2udebug import get_logger
from helpers.office365_test_helpers import azuretestdomain

@pytest.fixture
def broken_adconnection_folder_alias():
	"""
	Create broken azure account directory by copying azuretestdomain
	and overwriting the ids.json file with broken data.
	Yield the alias to the test.
	And clean up afterwards.
	"""
	alias = "brokenazuredomain"
	src_directory = Path(azuretestdomain[1])
	dst_directory = src_directory.parent / alias

	shutil.copytree(src_directory, dst_directory)
	ids_json = {
		"domain": "univention-azure-tests.de",
		"client_id": "2cc57918-30d7-47df-9aef",
		"adconnection_id": "d66c72f6-8dee-47ed-ac2b-7fdbe8b8a5d4",
		"reply_url": "https://10.200.29.80/univention/command/office365/authorize"
	}

	with open(f"{dst_directory / 'ids.json'}", 'w') as f:
		json.dump(ids_json, f)

	yield alias

	shutil.rmtree(dst_directory)


def test_broken_adconnection_config(broken_adconnection_folder_alias):
	"""
	- copy azureconnection folder
	- overwrite ids.json
	- set ucr variables correctly
	- Initialize UserConnector and see if it falls over
	- If it doesnt. test the get_core method
	- and the initialization of the MSGraphApiCore which should fail with a specific MSGraphError
	"""

	logger = get_logger("office365", "o365-user")

	connector = UserConnector(logger=logger)

	empty_core = connector.get_core(broken_adconnection_folder_alias)
	assert empty_core is None
	
	functioning_alias, _ = azuretestdomain
	functioning_core = connector.get_core(functioning_alias)
	assert functioning_core

	account = AzureAccount(broken_adconnection_folder_alias)
	with pytest.raises(MSGraphError):
		core = MSGraphApiCore(account, logger=logger)
