# -*- coding: utf-8 -*-
#
# Univention Office 365 - test_azure_object
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

import contextlib
import gzip
import json
import random
import string
import sys
import time
import uuid
import os
import pytest
import requests
import vcr
from mock import mock
from typing import Optional, Any, Dict


from test.utils import all_methods_called

pwd_module = mock.MagicMock()
m = mock.Mock()
m.pw_uid = 1000
pwd_module.getpwnam.return_value = m
sys.modules['pwd'] = pwd_module

# Mocking grp.getgrnam("nogroup").gr_gid
grp_module = mock.MagicMock()
m = mock.Mock()
m.gr_gid = 1000
grp_module.getgrnam.return_value = m
sys.modules['grp'] = grp_module

sys.modules['univention.debug'] = mock.MagicMock()
sys.modules['univention.config_registry'] = mock.MagicMock()
sys.modules['univention.lib.i18n'] = mock.MagicMock()
sys.modules['univention.config_registry.frontend'] = mock.MagicMock()
sys.modules['os'].chown = mock.MagicMock()

from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError
from univention.office365.microsoft.objects.azureobjects import UserAzure, GroupAzure, TeamAzure, SubscriptionAzure
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.core import MSGraphApiCore, URLs
from test import ALIASDOMAIN, DOMAIN_PATH, DOMAIN, OWNER_ID, VCR_PATH

URLs.proxies = mock.MagicMock(return_value={})

azure_user_selection = ["assignedLicenses",
				 "otherMails",
				 "businessPhones",
				 "displayName",
				 "givenName",
				 "jobTitle",
				 "mail",
				 "mobilePhone",
				 "officeLocation",
				 "preferredLanguage",
				 "surname",
				 "userPrincipalName",
				 "id",
				 "accountEnabled",
				 "onPremisesImmutableId",
				 "mailNickname",
				 "city",
				 "usageLocation",
				 "postalCode",
				 "streetAddress",
				 "assignedPlans"
				]


@contextlib.contextmanager
def new_user(core, name):
	# type: (MSGraphApiCore, str) -> UserAzure
	username = "user_{team_name}".format(team_name=name)
	user_email = "{username}@{domain}".format(username=username, domain=DOMAIN)

	user = UserAzure(onPremisesImmutableId=str(uuid.uuid4()),
					 accountEnabled=True,
					 displayName=username,
					 mailNickname=username,
					 userPrincipalName=user_email,
					 passwordProfile={
						 "forceChangePasswordNextSignIn": True,
						 "password": "1*#" + "".join(random.choices(string.ascii_letters, k=10))
					 },
					 usageLocation="DE")
	user.set_core(core)
	try:
		user.create()
	except MSGraphError as e:
		if "ObjectConflict" in e.args[0]:
			print("WARNING: User already exists, skipping creation. It will be deleted later but it indicates that a test have been badly stopped.")
			result_user = core.get_user(user_email)
			user._update_from_dict(result_user)
	try:
		yield user
	finally:
		user.delete()


@contextlib.contextmanager
def new_team_from_group(core, team_name):
	# type: (MSGraphApiCore, str) -> TeamAzure
	with new_user(core, team_name) as user:
		with new_group(core, team_name) as group:
			group.add_owner(user.id)
			team = TeamAzure.create_from_group(core, group.id)
			if team.isArchived:
				team.reactivate()
			try:
				team.wait_for_team()
				yield team
			finally:
				team.delete()


@contextlib.contextmanager
def new_team(core, team_name, owner):
	# type: (MSGraphApiCore, str, str) -> TeamAzure
	team = TeamAzure(displayName=team_name, description="Description of {description}".format(description=team_name))
	team.set_owner(owner)
	team.set_core(core)
	team.create()
	try:
		team.wait_for_team()
		yield team
	finally:
		team.delete()



@contextlib.contextmanager
def new_group(core, group_name):
	# type: (MSGraphApiCore, str) -> GroupAzure
	description = "Description of {group_name}".format(group_name=group_name)
	group = GroupAzure(
		description=description,
		displayName=group_name,
		mailEnabled=False,
		mailNickname=group_name.replace(" ", "_-_"),
		securityEnabled=True
	)
	group.set_core(core)
	group.create()
	try:
		yield group
	finally:
		pass
		if group.description != "deleted group":
			group.deactivate()


def check_code_internal(response):
	# type: (Dict[str, Any]) -> Optional[Dict[str, Any]]
	if response["status"]["code"] < 300 and response["status"]["code"] >= 200:
		json_response = {} if len(response["body"]["string"]) == 0 else json.loads(gzip.decompress(response["body"]["string"]))
		if "status" not in json_response or ("status" in json_response and json_response["status"] == "succeeded"):
			return response
	return None


my_vcr = vcr.VCR(
	filter_headers=[('Authorization', 'XXXXXX')],
	before_record_response=check_code_internal,
	# decode_compressed_response=True
)


class TestObjectAzure:

	def setup(self):
		""" """
		try:
			self.account = AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
		except FileNotFoundError as exc:
			print("FileNotFoundError: {exc}".format(exc=exc))
			pytest.exit(
				"FAIL: No testing files found in {} for domain {}. Skipping all tests".format(DOMAIN_PATH, ALIASDOMAIN))

		self.core = MSGraphApiCore(self.account)


class TestUserAzure(TestObjectAzure):

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, UserAzure, ["get_not_none_values_as_dict", "set_core", "wait_for_operation", "get_fields", "create_or_modify"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_create.yml'))
	def test_create(self):
		# type: () -> None
		""""""
		username = "test_create"
		with new_user(self.core, username) as user:
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert user.id == user_get.id

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_delete.yml'))
	def test_delete(self):
		# type: () -> None
		""""""
		username = "test_delete"
		user_id = None
		with new_user(self.core, username) as user:
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert user.id == user_get.id
			user_id = user.id
		user = UserAzure.get(self.core, user_id, selection=azure_user_selection)
		assert "ZZZ_delete" in user.displayName

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_update.yml'))
	def test_update(self):
		# type: () -> None
		""""""
		username = "test_update"
		with new_user(self.core, username) as user:
			user.update(UserAzure(postalCode="10004"))
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert user_get.postalCode == user.postalCode

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_deactivate.yml'))
	def test_deactivate(self):
		# type: () -> None
		""""""
		username = "test_deactivate"
		with new_user(self.core, username) as user:
			user.deactivate()
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert user_get.accountEnabled == False

	@pytest.mark.skip
	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_get_token_fail_directory_id_not_existtest_reactivate.yml'))
	def test_reactivate(self):
		# type: () -> None
		""""""
		username = "test_reactivate"
		with new_user(self.core, username) as user:
			user.deactivate()
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert user_get.accountEnabled == False
			user.reactivate()
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert user_get.accountEnabled == True

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_get.yml'))
	def test_get(self):
		# type: () -> None
		username = "test_get"
		with new_user(self.core, username) as user:
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert user.id == user_get.id

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_member_of.yml'))
	def test_member_of(self):
		# type: () -> None
		""""""
		name = "test_member_of"
		with new_group(self.core, name) as group:
			with new_user(self.core, name) as user:
				group.add_member(user.id)
				assert group.id in [x.id for x in user.member_of()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_list.yml'))
	def test_list(self):
		# type: () -> None
		""""""
		username = "test_list"
		with new_user(self.core, username) as user:
			users = UserAzure.list(self.core)
			assert user.id in [x.id for x in users]

	@pytest.mark.skip
	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_reset_password.yml'))
	def test_reset_password(self):
		# type: () -> None
		""""""
		username = "test_reset_password"
		with new_user(self.core, username) as user:
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			user.reset_password()
			assert user.passwordProfile["password"] != user_get.passwordProfile["password"]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_add_license.yml'))
	def test_add_license(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_add_license") as user:  # type: UserAzure
			subs_sku = SubscriptionAzure.list(self.core)
			for sku in subs_sku:
				if sku.has_free_seats():
					subs_sku = sku
					break

			user.add_license(subs_sku=subs_sku)
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert subs_sku.skuId in [x["skuId"] for x in user_get.assignedLicenses]
			user.remove_license(subs_sku=subs_sku)

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_invalidate_all_tokens.yml'))
	def test_invalidate_all_tokens(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_add_license") as user:  # type: UserAzure
			user.invalidate_all_tokens()

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_remove_license.yml'))
	def test_remove_license(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_add_license") as user:  # type: UserAzure
			subs_sku = SubscriptionAzure.list(self.core)
			for sku in subs_sku:
				if sku.has_free_seats():
					subs_sku = sku
					break

			user.add_license(subs_sku=subs_sku)
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert subs_sku.skuId in [x["skuId"] for x in user_get.assignedLicenses]
			user.remove_license(subs_sku=subs_sku)
			user_get = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			assert subs_sku.skuId not in [x["skuId"] for x in user_get.assignedLicenses]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_get_assignedLicenses.yml'))
	def test_get_assignedLicenses(self):
		""""""
		with new_user(self.core, "test_get_assignedLicenses") as user:  # type: UserAzure
			subs_sku = SubscriptionAzure.list(self.core)
			for sku in subs_sku:
				if sku.has_free_seats():
					subs_sku = sku
					break
			user.add_license(subs_sku=subs_sku)
			assert len(list(user.get_assignedLicenses())) > 0
			user.remove_license(subs_sku=subs_sku)

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestUserAzure/test_get_by_onPremisesImmutableID.yml'))
	def test_get_by_onPremisesImmutableID(self):
		""""""
		with new_user(self.core, "onPremisesImmutableID") as user:  # type: UserAzure
			user = UserAzure.get(self.core, user.id, selection=azure_user_selection)
			user2 = UserAzure.get_by_onPremisesImmutableID(self.core, user.onPremisesImmutableId)
			assert user.id == user2.id

class TestGroupAzure(TestObjectAzure):

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, GroupAzure, ["get_not_none_values_as_dict", "set_core", "wait_for_operation", "add_license", "remove_license", "get_fields", "create_or_modify"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_create.yml'))
	def test_create(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_create") as group:
			assert isinstance(group, GroupAzure)

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_delete.yml'))
	def test_delete(self):
		# type: () -> None
		""""""
		group_id = None
		with new_group(self.core, "test_delete") as group:
			assert isinstance(group, GroupAzure)
			group_id = group.id
		group_get = GroupAzure.get(self.core, group_id)
		assert "ZZZ_delete" in group_get.displayName

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_is_delete.yml'))
	def test_is_delete(self):
		# type: () -> None
		with new_group(self.core, "test_is_delete") as group:
			assert isinstance(group, GroupAzure)
			assert not group.is_delete()
			group_id = group.id
		group_get = GroupAzure.get(self.core, group_id)
		assert group_get.is_delete()

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_update.yml'))
	def test_update(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_update") as group:
			new_description = "New description of test_update"
			group.update(GroupAzure(description=new_description))
			group_get = GroupAzure.get(self.core, group.id)
			assert new_description in group_get.description

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_deactivate.yml'))
	def test_deactivate(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_deactivate") as group:
			group.deactivate()
			group_get = GroupAzure.get(self.core, group.id)
			assert "ZZZ_deleted" in group_get.displayName

	@pytest.mark.skip
	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_get_token_fail_directory_id_not_existtest_reactivate.yml'))
	def test_reactivate(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_update") as group:
			group.deactivate()
			group_get = GroupAzure.get(self.core, group.id)
			assert "ZZZ_deleted" not in group_get.displayName

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_add_member.yml'))
	def test_add_member(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_add_member") as user:
			with new_group(self.core, "test_add_member") as group:
				group.add_member(user.id)
				assert group.id in [x.id for x in user.member_of()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_add_owner.yml'))
	def test_add_owner(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_add_member") as user:
			with new_group(self.core, "test_add_member") as group:
				group.add_owner(user.id)
				assert user.id in [x.id for x in group.list_owners()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_remove_member.yml'))
	def test_remove_member(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_remove_member") as user:
			with new_group(self.core, "test_remove_member") as group:
				group.add_member(user.id)
				assert group.id in [x.id for x in user.member_of()]
				group.remove_member(user.id)
				assert group.id not in [x.id for x in user.member_of()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_remove_owner.yml'))
	def test_remove_owner(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_remove_member") as user:
			with new_user(self.core, "test_remove_member2") as user2:
				with new_group(self.core, "test_remove_member") as group:
					group.add_owner(user.id)
					group.add_owner(user2.id)
					assert user.id in [x.id for x in group.list_owners()]
					assert user2.id in [x.id for x in group.list_owners()]
					group.remove_owner(user.id)
					assert user.id not in [x.id for x in group.list_owners()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_list_members.yml'))
	def test_list_members(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_list_members") as user:
			with new_group(self.core, "test_list_members") as group:
				group.add_member(user.id)
				assert user.id in [x.id for x in group.list_members()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_list_owners.yml'))
	def test_list_owners(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_list_members") as user:
			with new_group(self.core, "test_list_members") as group:
				group.add_owner(user.id)
				assert user.id in [x.id for x in group.list_owners()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_get.yml'))
	def test_get(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_update") as group:
			group_get = GroupAzure.get(self.core, group.id)
			assert group_get.id in group.id

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_list.yml'))
	def test_list(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_update") as group:
			groups = GroupAzure.list(self.core)
			assert group.id in [x.id for x in groups]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_remove_direct_members.yml'))
	def test_remove_direct_members(self):
		# type: () -> None
		with new_group(self.core, "remove_direct_members") as group:
			with new_user(self.core, "remove_direct_members") as user:
				group.add_member(user.id)
				assert group.id in [x.id for x in user.member_of()]
				group.remove_direct_members()
				assert group.id not in [x.id for x in user.member_of()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_list_members_id.yml'))
	def test_list_members_id(self):
		# type: () -> None
		with new_group(self.core, "test_list_members_id") as group:
			with new_user(self.core, "test_list_members_id") as user:
				group.add_member(user.id)
				assert user.id in group.list_members_id()

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_exist.yml'))
	def test_exist(self):
		# type: () -> None
		with new_group(self.core, "test_exist") as group:
			assert group.exist()
		fake_group = GroupAzure(displayName="fake_displayName")
		fake_group.set_core(self.core)
		assert not fake_group.exist()

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_add_members.yml'))
	def test_add_members(self):
		# type: () -> None
		with new_group(self.core, "test_add_members") as group:
			with new_user(self.core, "test_add_members") as user:
				with new_user(self.core, "test_add_members2") as user2:
					assert user.id not in group.list_members_id()
					assert user2.id not in group.list_members_id()
					group.add_members([user.id, user2.id])
					assert user.id in group.list_members_id()
					assert user2.id in group.list_members_id()

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_member_of.yml'))
	def test_member_of(self):
		# type: () -> None
		""""""
		name = "test_member_of"
		with new_group(self.core, name+"1") as group1:
			with new_group(self.core, name+"2") as group2:
				group1.add_member(group2.id)
				assert group1.id in [x.id for x in group2.member_of()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestGroupAzure/test_get_by_name.yml'))
	def test_get_by_name(self):
		# type: () -> None
		""""""
		name = "test_get_by_name"
		with new_group(self.core, name) as group:
			group_by_name = GroupAzure.get_by_name(self.core, group.displayName)
			assert group_by_name.id == group.id


class TestTeamAzure(TestObjectAzure):

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, TeamAzure, ["get_not_none_values_as_dict", "set_core", "wait_for_operation", "wait_for_team", "add_license", "invalidate_all_tokens", "get_fields", "remove_license", "member_of", "create_from_group_async"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_set_owner.yml'))
	def test_set_owner(self):
		# type: () -> None
		""""""
		team = TeamAzure()
		team.set_owner("owner_id")
		assert team._owner_id == "owner_id"

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_create.yml'))
	def test_create(self):
		# type: () -> None
		""""""
		with new_team(self.core, "test_create", OWNER_ID) as team:
			time_slept = 0
			while True:
				try:
					teams = TeamAzure.list(self.core)
					if team.id in [x.id for x in teams]:
						break
				except MSGraphError as e:
					print(e)
					time.sleep(10)
					time_slept += 10
					if time_slept >= 180:
						raise

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_create_from_group.yml'))
	def test_create_from_group(self):
		# type: () -> None
		""""""
		with new_team_from_group(self.core, "test_create_from_group") as team:
			time_slept = 0
			while True:
				teams = TeamAzure.list(self.core)
				if team.id in [x.id for x in teams]:
					break
				else:
					time.sleep(10)
					time_slept += 10
					if time_slept >= 180:
						raise Exception("Team id not in list of teams")

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_delete.yml'))
	def test_delete(self):
		# type: () -> None
		""""""
		with new_team_from_group(self.core, "test_create") as team:
			pass
		time_slept = 0
		while True:
				team = TeamAzure.get(self.core, team.id)
				if "ZZZ_delete" in team.displayName:
					break
				time.sleep(10)
				time_slept += 10
				if time_slept >= 180:
					raise Exception("Team not deleted. It took more than 180 seconds")

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_update.yml'))
	def test_update(self):
		# type: () -> None
		""""""
		with new_team_from_group(self.core, "test_update") as team:
			time_slept = 0
			while True:
				try:
					changes = TeamAzure(description="New_description")
					team.update(changes)
					break
				except MSGraphError as e:
					print(e)
					time.sleep(10)
					time_slept += 10
					if time_slept >= 180:
						raise
			time_slept = 0
			while True:
				try:
					team_get = TeamAzure.get(self.core, team.id)
					assert changes.description in team_get.description
					break
				except MSGraphError as e:
					print(e)
					time.sleep(10)
					time_slept += 10
					if time_slept >= 180:
						raise

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_deactivate.yml'))
	def test_deactivate(self):
		# type: () -> None
		""""""
		with new_team_from_group(self.core, "test_deactivate") as team:
			team.deactivate()
			team_get = TeamAzure.get(self.core, team.id)
			assert team_get.isArchived
			team.reactivate()
			while True:
				team_get = TeamAzure.get(self.core, team.id)
				if not team_get.isArchived:
					break
				time.sleep(10)

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_reactivate.yml'))
	def test_reactivate(self):
		# type: () -> None
		""""""
		with new_team_from_group(self.core, "test_reactivate") as team:
			team.deactivate()
			team_get = TeamAzure.get(self.core, team.id)
			assert team_get.isArchived
			team.reactivate()
			team_get = TeamAzure.get(self.core, team.id)
			assert not team_get.isArchived

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_add_member.yml'))
	def test_add_member(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_add_member2") as user2:
			with new_team_from_group(self.core, "test_add_member") as team:
				team.add_member(user2.id)
				assert user2.id in [x.id for x in team.list_team_members()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_add_members.yml'))
	def test_add_members(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_add_members2") as user2:
			with new_team_from_group(self.core, "test_add_members") as team:
				team.add_members([user2.id])
				assert user2.id in [x.id for x in team.list_team_members()]

	# @pytest.mark.skip
	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_delete_member.yml'))
	def test_delete_member(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_delete_member1") as user2:
			with new_team_from_group(self.core, "test_delete_member") as team:
				response = team.add_member(user2.id)
				assert user2.id in [x.id for x in team.list_team_members()]
				while True:
					try:
						team.delete_member(response["id"])
						break
					except MSGraphError as e:
						if not(hasattr(e.response, "json") and e.response.json().get("error", {}).get("code", None) == "Forbidden"):
							raise
						time.sleep(10)
				assert user2.id not in [x.id for x in team.list_team_members()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_list_team_members.yml'))
	def test_list_team_members(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_list_team_members1") as user2:
			with new_team_from_group(self.core, "test_list_team_members") as team:
				team.add_member(user2.id)
				assert user2.id in [x.id for x in team.list_team_members()]

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_list.yml'))
	def test_list(self):
		# type: () -> None
		""""""
		with new_team_from_group(self.core, "test_list") as team:
			while True:
				teams = TeamAzure.list(self.core)
				if team.id in [x.id for x in teams]:
					break
				else:
					time.sleep(10)

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestTeamAzure/test_get.yml'))
	def test_get(self):
		# type: () -> None
		""""""
		with new_team_from_group(self.core, "test_get") as team:
			team_get = TeamAzure.get(self.core, team.id)
			assert team_get.id == team.id


class TestSubscriptionAzure(TestObjectAzure):

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, SubscriptionAzure, ["get_not_none_values_as_dict", "set_core", "wait_for_operation", "reactivate", "deactivate", "delete", "create", "update", "add_license", "get_fields", "remove_license", "member_of"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestSubscriptionAzure/test_get.yml'))
	def test_get(self):
		# type: () -> None
		test_default_id = "3e7d9eb5-c3a1-4cfc-892e-a8ec29e45b77_6fd2c87f-b296-42f0-b197-1e91e994b900"
		sku = SubscriptionAzure.get(self.core, test_default_id)
		sku.id = test_default_id

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestSubscriptionAzure/test_list.yml'))
	def test_list(self):
		# type: () -> None
		subs = SubscriptionAzure.list(self.core)
		assert len(subs) > 0

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestSubscriptionAzure/test_get_enabled.yml'))
	def test_get_enabled(self):
		# type: () -> None
		_default_azure_service_plan_names = "SHAREPOINTWAC, SHAREPOINTWAC_DEVELOPER, OFFICESUBSCRIPTION, OFFICEMOBILE_SUBSCRIPTION, SHAREPOINTWAC_EDU"

		subs_enambled = SubscriptionAzure.get_enabled(self.core, _default_azure_service_plan_names)
		assert len(subs_enambled) > 0

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestSubscriptionAzure/test_has_free_seats.yml'))
	def test_has_free_seats(self):
		# type: () -> None
		""""""
		subs = SubscriptionAzure.list(self.core)[0]
		assert isinstance(subs.has_free_seats(), bool)

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestSubscriptionAzure/test_get_plans_id_from_names.yml'))
	def test_get_plans_id_from_names(self):
		# type: () -> None
		""""""
		subs = SubscriptionAzure.list(self.core)[0]
		names = subs.get_plans_names()
		ids = subs.get_plans_id_from_names(names)
		assert len(ids) == len(names)
		assert isinstance(names, list)
		assert isinstance(names[0], str)

	@my_vcr.use_cassette(os.path.join(VCR_PATH, 'TestSubscriptionAzure/test_get_plans_names.yml'))
	def test_get_plans_names(self):
		# type: () -> None
		""""""
		subs = SubscriptionAzure.list(self.core)[0]
		names = subs.get_plans_names()
		assert isinstance(names, list)
		assert isinstance(names[0], str)
