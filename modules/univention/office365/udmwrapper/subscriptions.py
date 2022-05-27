#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle subscription profiles
#
# Copyright 2016-2021 Univention GmbH
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
from typing import List, Optional

from univention.office365.udm_helper import UDMHelper
from univention.office365.logging2udebug import get_logger


logger = get_logger("office365", "o365")


class SubscriptionProfile(object):
	def __init__(self, name, subscription=None, whitelisted_plans=None, blacklisted_plans=None):
		# type: (str, Optional[], Optional[List[str]], Optional[List[str]]) -> None
		self.name = name
		self.subscription = subscription  # skuPartNumber
		self.whitelisted_plans = whitelisted_plans or list()
		self.blacklisted_plans = blacklisted_plans or list()

	def __repr__(self):
		# type: () -> str
		return 'SubscriptionProfile({}: {})'.format(self.name, self.subscription)

	@classmethod
	def load(cls, dn):
		# type: (str) -> SubscriptionProfile
		"""
		Load a subscription profile.

		:param dn: str: DN of profile
		:return: a SubscriptionProfile object
		"""
		profile = UDMHelper().get_udm_officeprofile(dn)
		logger.debug('loading profile: %r, with settings %r', dn, dict(profile))
		return cls(
			name=profile.get('name'),
			subscription=profile.get('subscription'),
			whitelisted_plans=profile.get('whitelisted_plans'),
			blacklisted_plans=profile.get('blacklisted_plans'))

	@staticmethod
	def list_profiles():
		# type: () -> List[SubscriptionProfile]
		return UDMHelper().list_udm_office_profiles()

	@classmethod
	def get_profiles_for_groups(cls, dns):
		# type: (List[str]) -> List[SubscriptionProfile]
		"""
		Retrieve subscription profiles for groups.

		:param dns: list of group DNs [str, str, ..]
		:return: list of SubscriptionProfile objects
		"""
		# collect extended attribute values from groups
		profiles = list()
		for dn in dns:
			group = UDMHelper().get_udm_group(dn)
			try:
				profile = group['UniventionOffice365Profile']
				if profile:
					profiles.append(profile)
			except KeyError:
				logger.debug('No Profile for group %r.', dn)
				pass

		# load SubscriptionProfiles
		return [cls.load(p) for p in profiles]
