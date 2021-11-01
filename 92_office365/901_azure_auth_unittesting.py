#!/usr/share/ucs-test/runner pytest
## -*- coding: utf-8 -*-
## desc: unit test for azure auth
## tags: [apptest]
## exposure: dangerous
## packages:
##   - univention-office365


import pytest
from univention.office365 import azure_auth


def test_get_conf_path():
	with pytest.raises(ValueError):
		azure_auth.AzureADConnectionHandler.get_conf_path("CONFDIR", None)


def test_listener_restart(monkeypatch, mocker):
	mocker.patch('univention.office365.azure_auth.subprocess.call')
	azure_auth.AzureADConnectionHandler.listener_restart()
	azure_auth.subprocess.call.assert_called_once_with(['systemctl', 'restart', 'univention-directory-listener'])

def test_get_adconnection_aliases(mocker):
	mocker.patch('univention.office365.azure_auth.ucr')
	mocker.patch('univention.office365.azure_auth.ucr.items',
				 return_value=[(azure_auth.adconnection_alias_ucrv + "foo1", "bar1")])
	assert azure_auth.AzureADConnectionHandler.get_adconnection_aliases() == {"foo1": "bar1"}
	azure_auth.ucr.load.assert_called_once()
	azure_auth.ucr.items.assert_called_once()


def test_adconnection_id_to_alias(mocker):
	mocker.patch('univention.office365.azure_auth.ucr')
	mocker.patch('univention.office365.azure_auth.ucr.items', return_value=[(azure_auth.adconnection_alias_ucrv+"foo1", "bar1")])
	assert azure_auth.AzureADConnectionHandler.adconnection_id_to_alias("bar1") == "foo1"
	azure_auth.ucr.load.assert_called_once()
	azure_auth.ucr.items.assert_called_once()

# def test_get_adconnections(mocker):
#     mocker.patch('univention.office365.azure_auth.ucr')
#     mocker.patch('univention.office365.azure_auth.ucr.items', return_value=[(azure_auth.adconnection_alias_ucrv+"foo1", "bar1"), (azure_auth.adconnection_alias_ucrv+"foo2", "bar2")])
#     assert azure_auth.AzureADConnectionHandler.get_adconnections() == {"foo1": "bar1", "foo2": "bar2"}
#     azure_auth.ucr.load.assert_called_once()
#     azure_auth.ucr.items.assert_called_once()
