# -*- coding: utf-8 -*-
#
# Univention Office 365 - __init__
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only


import os

ASYNC_DATA_DIR = '/var/lib/univention-office365/async'
ASYNC_FAILED_DIR = os.path.join(ASYNC_DATA_DIR, 'failed')
