# -*- coding: utf-8 -*-
#
# Univention Office 365 - test_ucr_helper
#
# SPDX-FileCopyrightText: 2026 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

import importlib.util
import os
import sys
import types
from unittest import mock

import pytest


PROXY_ENV_KEYS = ('http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY', 'no_proxy', 'NO_PROXY')


class FakeConfigRegistry(dict):
    def load(self):
        pass

    def is_true(self, key, default=False):
        return default


@pytest.fixture
def ucr_helper_module(monkeypatch):
    config_registry = types.ModuleType('univention.config_registry')
    config_registry.ConfigRegistry = FakeConfigRegistry
    config_registry.handler_set = mock.MagicMock()
    config_registry.handler_unset = mock.MagicMock()

    frontend = types.ModuleType('univention.config_registry.frontend')
    frontend.ucr_update = mock.MagicMock()

    monkeypatch.setitem(sys.modules, 'univention.config_registry', config_registry)
    monkeypatch.setitem(sys.modules, 'univention.config_registry.frontend', frontend)

    module_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'modules', 'univention', 'office365', 'ucr_helper.py')
    spec = importlib.util.spec_from_file_location('ucr_helper_under_test', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def clear_proxy_env(monkeypatch):
    for env_key in PROXY_ENV_KEYS:
        monkeypatch.delenv(env_key, raising=False)


def test_get_proxy_subprocess_env_preserves_environment_proxy_values(ucr_helper_module, monkeypatch):
    monkeypatch.setenv('HTTP_PROXY', 'http://upper.example:3128')
    monkeypatch.setenv('http_proxy', 'http://lower.example:3128')
    monkeypatch.setenv('HTTPS_PROXY', 'https://upper.example:3128')
    monkeypatch.setenv('NO_PROXY', 'upper.example')
    monkeypatch.setenv('no_proxy', 'lower.example')
    monkeypatch.setenv('OTHER_ENV', 'preserved')

    env = ucr_helper_module.UCRHelperC().get_proxy_subprocess_env(mock.MagicMock())

    assert env['http_proxy'] == 'http://lower.example:3128'
    assert env['HTTP_PROXY'] == 'http://lower.example:3128'
    assert env['https_proxy'] == 'https://upper.example:3128'
    assert env['HTTPS_PROXY'] == 'https://upper.example:3128'
    assert env['no_proxy'] == 'lower.example'
    assert env['NO_PROXY'] == 'lower.example'
    assert env['OTHER_ENV'] == 'preserved'


def test_get_proxy_subprocess_env_prefers_system_ucr_proxy_values(ucr_helper_module, monkeypatch):
    monkeypatch.setenv('http_proxy', 'http://env.example:3128')
    monkeypatch.setenv('https_proxy', 'https://env.example:3128')
    ucr = ucr_helper_module.UCRHelperC(
        {
            'proxy/http': 'http://ucr.example:3128',
            'proxy/https': 'https://ucr.example:3128',
        }
    )

    env = ucr.get_proxy_subprocess_env(mock.MagicMock())

    assert env['http_proxy'] == 'http://ucr.example:3128'
    assert env['HTTP_PROXY'] == 'http://ucr.example:3128'
    assert env['https_proxy'] == 'https://ucr.example:3128'
    assert env['HTTPS_PROXY'] == 'https://ucr.example:3128'


def test_get_proxy_subprocess_env_prefers_office365_proxy_values(ucr_helper_module):
    ucr = ucr_helper_module.UCRHelperC(
        {
            'proxy/http': 'http://system.example:3128',
            'proxy/https': 'https://system.example:3128',
            'office365/proxy/http': 'http://office365.example:3128',
            'office365/proxy/https': 'https://office365.example:3128',
        }
    )

    env = ucr.get_proxy_subprocess_env(mock.MagicMock())

    assert env['http_proxy'] == 'http://office365.example:3128'
    assert env['HTTP_PROXY'] == 'http://office365.example:3128'
    assert env['https_proxy'] == 'https://office365.example:3128'
    assert env['HTTPS_PROXY'] == 'https://office365.example:3128'


def test_get_proxy_subprocess_env_office365_ignore_removes_inherited_proxy_values(ucr_helper_module, monkeypatch):
    monkeypatch.setenv('http_proxy', 'http://env.example:3128')
    monkeypatch.setenv('HTTPS_PROXY', 'https://env.example:3128')
    ucr = ucr_helper_module.UCRHelperC(
        {
            'proxy/http': 'http://system.example:3128',
            'proxy/https': 'https://system.example:3128',
            'office365/proxy/http': 'ignore',
            'office365/proxy/https': 'ignore',
        }
    )

    env = ucr.get_proxy_subprocess_env(mock.MagicMock())

    assert 'http_proxy' not in env
    assert 'HTTP_PROXY' not in env
    assert 'https_proxy' not in env
    assert 'HTTPS_PROXY' not in env


def test_get_proxy_subprocess_env_sets_no_proxy_from_ucr(ucr_helper_module, monkeypatch):
    monkeypatch.setenv('no_proxy', 'env.example')
    ucr = ucr_helper_module.UCRHelperC({'proxy/no_proxy': 'localhost,127.0.0.1'})

    env = ucr.get_proxy_subprocess_env(mock.MagicMock())

    assert env['no_proxy'] == 'localhost,127.0.0.1'
    assert env['NO_PROXY'] == 'localhost,127.0.0.1'
