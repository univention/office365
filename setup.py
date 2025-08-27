#!/usr/bin/python3
# SPDX-FileCopyrightText: 2022-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

import io
from setuptools import setup
from email.utils import parseaddr
from debian.changelog import Changelog
from debian.deb822 import Deb822

dch = Changelog(io.open('debian/changelog', 'r', encoding='utf-8'))
dsc = Deb822(io.open('debian/control', 'r', encoding='utf-8'))
realname, email_address = parseaddr(dsc['Maintainer'])

setup(
    packages=[
        'univention.office365',
        'univention.office365.asyncqueue',
        'univention.office365.asyncqueue.queues',
        'univention.office365.asyncqueue.tasks',
        'univention.office365.connector',
        'univention.office365.microsoft',
        'univention.office365.microsoft.exceptions',
        'univention.office365.microsoft.objects',
        'univention.office365.udmwrapper',
        'univention.office365.utils',
    ],
    package_dir={'': 'modules'},
    description='Univention Office365',
    url='https://www.univention.de/',
    license='GNU Affero General Public License v3',
    name=dch.package,
    version=dch.version.full_version,
    maintainer=realname,
    maintainer_email=email_address,
)
