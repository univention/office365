# -*- coding: utf-8 -*-
#
# Univention Office 365 - __init__
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

import json
import os
import sys
import tempfile
import shutil
import uuid
from datetime import datetime, timedelta

import mock

ALIASDOMAIN = 'o365-dev-univention-de'
ALIASDOMAIN_2 = 'o365domain'
# ALIASDOMAIN = "u-azure-test-de"
DOMAIN_PATH = '/etc/univention-office365'
# DOMAIN = "alphadistrict.onmicrosoft.com"
DOMAIN = 'univentiontestgmbh.onmicrosoft.com'
DOMAIN_2 = 'office365.dev-univention.de'
OWNER_ID = str(uuid.uuid4())
VCR_PATH = os.path.join(os.path.dirname(__file__), 'vcr_cassettes')


def write(path, data):
    with open(path, 'w') as f:
        json.dump(data, f)


if os.path.exists(os.path.join(DOMAIN_PATH, ALIASDOMAIN)) and not os.path.exists(os.path.join(DOMAIN_PATH, ALIASDOMAIN_2)):
    NEW_DOMAIN_PATH = tempfile.mkdtemp('-univention-office365')
    shutil.copytree(os.path.join(DOMAIN_PATH, ALIASDOMAIN), os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN))
    shutil.copytree(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN), os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN_2))
    DOMAIN_PATH = NEW_DOMAIN_PATH
elif not os.path.exists(os.path.join(DOMAIN_PATH, ALIASDOMAIN_2)) or not not os.path.exists(os.path.join(DOMAIN_PATH, ALIASDOMAIN)):
    NEW_DOMAIN_PATH = tempfile.mkdtemp('-univention-office365')
    os.mkdir(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN))
    DOMAIN_2 = 'test_domain.de'
    write(
        os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, 'ids.json'),
        data={'domain': DOMAIN_2, 'client_id': str(uuid.uuid4()), 'adconnection_id': str(uuid.uuid4()), 'reply_url': 'https://10.200.29.86/univention/command/office365/authorize'},
    )
    write(
        os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, 'token.json'),
        data={
            'token_type': 'Bearer',
            'expires_in': 3599,
            'ext_expires_in': 3599,
            'access_token': str(uuid.uuid4()),
            'expires_on': (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S'),
        },
    )
    write(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, 'manifesst.json'), data={})
    with open(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, 'key.pem'), 'w') as f:
        pass
    with open(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, 'cert.pem'), 'w') as f:
        pass
    with open(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, 'cert.fp'), 'w') as f:
        pass
    rsa = mock.MagicMock()
    rsa.sign = mock.MagicMock(return_value=b'signature')
    sys.modules['rsa'] = rsa
    shutil.copytree(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN), os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN_2))
    DOMAIN_PATH = NEW_DOMAIN_PATH
