# -*- coding: utf-8 -*-
#
# Univention Office 365 - __init__
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only


from typing import Union


def bool_from_bytes(value):
    # type: (Union[bytes, str,int,bool]) -> None
    return bool(int(value))
