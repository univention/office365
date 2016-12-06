#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle subscription profiles
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

from univention.office365.azure_handler import get_service_plan_names


class SubscriptionProfile(object):
	def __init__(self, name, subscriptions=None, whitelisted_plans=None, blacklisted_plans=None):
		self.name = name
		self.subscriptions = subscriptions or list()  # skuPartNumber
		self.whitelisted_plans = whitelisted_plans or list()
		self.blacklisted_plans = blacklisted_plans or list()
		self._identifier = ''  # DN? file location? not needed?

	def __repr__(self):
		return 'SubscriptionProfile({}: {})'.format(self.name, self.subscriptions)

	@staticmethod
	def list():
		"""
		List all available subscription profiles.

		:return: list of 2-tuples (str, str): [(name, identifier), ..]
		"""
		# TODO: impl
		# mockup
		return [('All subscriptions but only office plans', '123abc'), ('Nothing', '0Null')]

	@staticmethod
	def load(identifier):
		"""
		Load a subscription profile.

		:param identifier: name? DN?
		:return: a SubscriptionProfile object
		"""
		# TODO: impl
		# mockup
		if identifier == 'a':
			obj = SubscriptionProfile('All subscriptions, activate only office plans.')
			obj.subscriptions = ['ENTERPRISEPACK', 'OFFICESUBSCRIPTION_FACULTY', 'OFFICESUBSCRIPTION_STUDENT']
			obj.whitelisted_plans = ['SHAREPOINTWAC', 'SHAREPOINTWAC_DEVELOPER', 'OFFICESUBSCRIPTION', 'SWAY']
			obj.blacklisted_plans = ['SWAY']
			obj._identifier = identifier
			return obj
		elif identifier == 'b':
			obj = SubscriptionProfile('All subscriptions, activate only SWAY plan.')
			obj.subscriptions = ['ENTERPRISEPACK', 'OFFICESUBSCRIPTION_FACULTY', 'OFFICESUBSCRIPTION_STUDENT']
			obj.whitelisted_plans = ['SWAY']
			obj._identifier = identifier
			return obj
		elif identifier == 'c':
			obj = SubscriptionProfile('All subscriptions, activate all but SWAY plan.')
			obj.subscriptions = ['ENTERPRISEPACK', 'OFFICESUBSCRIPTION_FACULTY', 'OFFICESUBSCRIPTION_STUDENT']
			obj.blacklisted_plans = ['SWAY']
			obj._identifier = identifier
			return obj
		else:
			obj = SubscriptionProfile('All subscriptions, activate all plans.')
			obj.subscriptions = ['ENTERPRISEPACK', 'OFFICESUBSCRIPTION_FACULTY', 'OFFICESUBSCRIPTION_STUDENT']
			obj._identifier = identifier
			return obj

	def store(self):
		"""
		Store this subscription profile.

		:return: bool? identifier? file location? DN?
		"""
		# TODO: impl
		return self._identifier

	@classmethod
	def get_profiles_for_groups(cls, dns, udm):
		"""
		Retrieve subscription profiles for groups.

		:param dns: list of group DNs [str, str, ..]
		:param udm: initialized UDMHelper instance
		:return: list of SubscriptionProfile objects
		"""
		# collect extended attribute values from groups
		profiles = list()
		for dn in dns:
			user = udm.get_udm_group(dn)
			try:
				profile = user['office365subscription']  # TODO: fix UDM attribute name
				if profile:
					profiles.append(profile)
			except KeyError:
				pass

		# mockup
		profiles = ['a', 'b', 'c', '']  # TODO: remove this

		# load SubscriptionProfiles
		return [cls.load(profile) for profile in profiles]
