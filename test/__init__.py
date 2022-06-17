# -*- coding: utf-8 -*-
#
# Univention Office 365 - __init__
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
import json
import os
import sys
import tempfile
import shutil
import uuid
from datetime import datetime, timedelta

import mock

ALIASDOMAIN = "o365-dev-univention-de"
ALIASDOMAIN_2 = "o365domain"
# ALIASDOMAIN = "u-azure-test-de"
DOMAIN_PATH = "/etc/univention-office365"
# DOMAIN = "alphadistrict.onmicrosoft.com"
DOMAIN = "univentiontestgmbh.onmicrosoft.com"
DOMAIN_2 = "office365.dev-univention.de"
OWNER_ID = str(uuid.uuid4())
VCR_PATH = os.path.join(os.path.dirname(__file__), "vcr_cassettes")


def write(path, data):
	with open(path, "w") as f:
		json.dump(data, f)


if os.path.exists(os.path.join(DOMAIN_PATH, ALIASDOMAIN)) and not os.path.exists(os.path.join(DOMAIN_PATH, ALIASDOMAIN_2)):
	NEW_DOMAIN_PATH = tempfile.mkdtemp("-univention-office365")
	shutil.copytree(os.path.join(DOMAIN_PATH, ALIASDOMAIN), os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN))
	shutil.copytree(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN), os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN_2))
	DOMAIN_PATH = NEW_DOMAIN_PATH
elif not os.path.exists(os.path.join(DOMAIN_PATH, ALIASDOMAIN_2)) or not not os.path.exists(os.path.join(DOMAIN_PATH, ALIASDOMAIN)):
	NEW_DOMAIN_PATH = tempfile.mkdtemp("-univention-office365")
	os.mkdir(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN))
	DOMAIN_2 = "test_domain.de"
	write(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, "ids.json"), data={"domain": DOMAIN_2, "client_id": str(uuid.uuid4()), "adconnection_id": str(uuid.uuid4()), "reply_url": "https://10.200.29.86/univention/command/office365/authorize"})
	write(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, "token.json"), data={"token_type": "Bearer", "expires_in": 3599, "ext_expires_in": 3599, "access_token": str(uuid.uuid4()), "expires_on": (datetime.today()+timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")})
	write(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, "manifesst.json"), data={})
	with open(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, "key.pem"), "w") as f:
		pass
	with open(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, "cert.pem"), "w") as f:
		pass
	with open(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN, "cert.fp"), "w") as f:
		pass
	rsa = mock.MagicMock()
	rsa.sign = mock.MagicMock(return_value=b"signature")
	sys.modules["rsa"] = rsa
	shutil.copytree(os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN), os.path.join(NEW_DOMAIN_PATH, ALIASDOMAIN_2))
	DOMAIN_PATH = NEW_DOMAIN_PATH
