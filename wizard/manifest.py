#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - manifest file manipulation
#
# Copyright 2016 Univention GmbH
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

import sys
import json
import uuid

txt = sys.stdin.read()
manifest = json.loads(txt)

cert = open("/etc/univention-office365/cert.pem", "r").read()
cert_split = cert.split("\n")
cert_start = 1  # TODO: verify by looking for -----BEGIN CERTIFICATE-----
cert_end = -2  # TODO: verify by looking for -----END CERTIFICATE-----
key = "".join(cert_split[cert_start:cert_end])
cert_fp = open("/etc/univention-office365/cert.fp", "r").read().strip()
keyCredentials = dict(
	customKeyIdentifier=cert_fp,
	keyId=str(uuid.uuid4()),
	type="AsymmetricX509Cert",
	usage="verify",
	value=key)

manifest["keyCredentials"].append(keyCredentials)
manifest["oauth2AllowImplicitFlow"] = True
manifest["requiredResourceAccess"][0]["resourceAccess"].append({
	"id": "78c8a3c8-a07e-4b9e-af1b-b5ccab50a175",
	"type": "Role"})

json.dump(manifest, sys.stdout, indent=2, separators=(',', ': '), sort_keys=True)
