#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle subscription profiles
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

from typing import List, Optional, Dict

from univention.office365.udm_helper import UDMHelper
from univention.office365.logging2udebug import get_logger


logger = get_logger('office365', 'o365')


class SubscriptionProfile(object):
    def __init__(self, name, subscription=None, whitelisted_plans=None, blacklisted_plans=None):
        # type: (str, Optional[Dict], Optional[List[str]], Optional[List[str]]) -> None
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
            blacklisted_plans=profile.get('blacklisted_plans'),
        )

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
