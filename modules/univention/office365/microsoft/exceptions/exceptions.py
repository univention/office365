# -*- coding: utf-8 -*-
#
# Univention Office 365 - exceptions
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only


# MS Graph specific errors =====================================================

"""
The GraphError class is kept very generic at this point. There will
probably be more specific error messages required in the future and for
that this file has already been prepared. That way we can keep the
adaptions required to introduce new error types smaller.
"""


class NoAllocatableSubscriptions(Exception):
    def __init__(self, user, adconnection_alias=None, *args, **kwargs):
        # type: ("UserAzure", str, List, Dict) -> None
        self.user = user
        self.adconnection_alias = adconnection_alias
        super(NoAllocatableSubscriptions, self).__init__(*args, **kwargs)


class GraphError(Exception):
    pass


class GraphRessourceNotFroundError(GraphError):
    pass


class MissingAzureUserId(Exception):
    """Either AzureID or UserPrincipal name needed by azure to specify the relevant user"""

    pass


# vim: filetype=python expandtab tabstop=4 shiftwidth=4 softtabstop=4
