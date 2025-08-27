#!/usr/share/ucs-test/runner pytest-3 -s -l -vv
## -*- coding: utf-8 -*-
## desc: Test that the Connector and it's get_core method fail gracefully when encountering a broken adconnection config
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365

import pytest
import shutil
import json
from pathlib import Path

from univention.office365.connector.connector import UserConnector, GroupConnector
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.logging2udebug import get_logger
from helpers.office365_test_helpers import azuretestdomain


BROKEN_ALIAS = 'brokenazuredomain'


@pytest.fixture(scope='module')
def broken_adconnection_directory():
    """
    Create broken azure account directory by copying azuretestdomain
    Yield the directory path to the test and clean up afterwards.
    """
    src_directory = Path(azuretestdomain[1])
    dst_directory = src_directory.parent / BROKEN_ALIAS
    shutil.copytree(src_directory, dst_directory)

    yield dst_directory

    shutil.rmtree(dst_directory)


@pytest.fixture(
    params=[('client_id', '66666666-6666-6666-6666-666666666666', 'broken_alias'), ('adconection_id', '44444444-4444-4444-4444-444444444444', None), ('reply_url', '', None)]
)
def add_broken_config_expected_return(request, ucr, broken_adconnection_directory):
    """Delete the token file and overwrite the ids.json file with broken data."""
    key, value, raise_error = request.param

    ucr.handler_set([f'office365/adconnection/alias/{BROKEN_ALIAS}=initialized'])

    with open(broken_adconnection_directory / 'token.json', 'w') as f:
        f.write('')

    ids_json_file = broken_adconnection_directory / 'ids.json'
    with open(ids_json_file, 'r') as f:
        ids_json = json.load(f)

    ids_json[key] = value

    with open(ids_json_file, 'w') as f:
        json.dump(ids_json, f)
    return raise_error


@pytest.mark.parametrize('Connector', [UserConnector, GroupConnector])
def test_broken_adconnection_config(add_broken_config_expected_return, Connector):
    """
    - Initialize UserConnector and see if it falls over
    - Test the get_core method, with broken and functioning adconnection.
    - Test the initialization of the MSGraphApiCore which should fail with an MSGraphError.
    """
    logger = get_logger('office365', 'o365-user')

    connector = Connector(logger=logger)

    empty_core = connector.get_core(BROKEN_ALIAS)
    assert empty_core is None

    functioning_alias, _ = azuretestdomain
    functioning_core = connector.get_core(functioning_alias)
    assert functioning_core

    account = AzureAccount(BROKEN_ALIAS)

    if add_broken_config_expected_return is None:
        return

    with pytest.raises(MSGraphError):
        core = MSGraphApiCore(account, logger=logger)
