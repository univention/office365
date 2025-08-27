# -*- coding: utf-8 -*-
#
# Univention Office 365 - utils
#
# SPDX-FileCopyrightText: 2016-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only


def all_methods_called(test_class, class_to_check, exclude):
    method_list = [func for func in dir(class_to_check) if callable(getattr(class_to_check, func)) and not func.startswith('_')]
    method_list2 = [func[5:] for func in dir(test_class) if callable(getattr(test_class, func)) and not func.startswith('_') and func.startswith('test_')]
    diff = set(method_list) - set(method_list2) - set(exclude)
    return diff
