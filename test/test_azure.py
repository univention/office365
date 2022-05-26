import gzip
import json
import random
import requests
import string
import sys
import time
import contextlib
import vcr
import test.mocking
import pytest
from mock import mock, patch
import requests_mock
from typing import Any, Dict, Optional

from test.utils import all_methods_called
from univention.office365.utils.utils import create_random_pw

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
sys.modules['univention.config_registry'].ConfigRegistry.get_http_proxies = mock.MagicMock()
sys.modules['univention.lib.i18n'] = mock.MagicMock()
sys.modules['univention.config_registry.frontend'] = mock.MagicMock()
sys.modules["os"].chown = mock.MagicMock()
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.urls import URLs
URLs.proxies = mock.MagicMock(return_value={})
from univention.office365.microsoft.core import MSGraphApiCore
from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError
from test import ALIASDOMAIN, DOMAIN_PATH, DOMAIN

@contextlib.contextmanager
def new_user(core, name):
	# type: (MSGraphApiCore, str) -> Dict[str, Any]
	username = "user_{team_name}".format(team_name=name)
	user_email = "{username}@{domain}".format(username=username, domain=DOMAIN)
	attr = {
		"accountEnabled": True,
		"displayName": username,
		"mailNickname": username,
		"userPrincipalName": user_email,
		"passwordProfile": {
			"forceChangePasswordNextSignIn": True,
			"password": "1" + "".join(random.choices(string.ascii_letters, k=10))
		},
		"usageLocation": "DE"
	}
	try:
		result_user = core.add_user(attr)
	except MSGraphError as e:
		if "ObjectConflict" in e.args[0]:
			print(
				"WARNING: User already exists, skipping creation. It will be deleted later but it indicates that a test have been badly stopped.")
			result_user = core.get_user(user_email)
		else:
			raise
	try:
		result_user["passwordProfile"] = attr["passwordProfile"]
		yield result_user
	finally:
		user = dict(accountEnabled=False,
					userPrincipalName="ZZZ_deleted_{time}_{orig}".format(time=time.time(), orig=user_email),
					displayName="ZZZ_deleted_{time}_{orig}".format(time=time.time(), orig=username))
		core.modify_user(oid=result_user["id"], user=user)


@contextlib.contextmanager
def new_team(core, team_name, owner):
	# type: (MSGraphApiCore, str, str) -> Dict[str, Any]
	with new_group(core, "group" + team_name) as group:
		core.add_group_owner(group["id"], owner)
		time_slept = 0
		while True:
			try:
				result_team = core.create_team_from_group(group["id"])
				break
			except MSGraphError:
				time.sleep(10)
				time_slept += 10
				if time_slept >= 180:
					raise
		try:
			yield result_team, group["id"]
		finally:
			while True:
				try:
					core.archive_team(group["id"])
					break
				except MSGraphError:
					time.sleep(10)


@contextlib.contextmanager
def new_group(core, group_name):
	# type: (MSGraphApiCore, str) -> Dict[str, Any]
	description = "Description of {group_name}".format(group_name=group_name)
	data = dict(
		description=description,
		displayName=group_name,
		mailEnabled=False,
		mailNickname=group_name.replace(" ", "_-_"),
		securityEnabled=True
	)
	result_group = core.create_group(data)
	try:
		yield result_group
	finally:
		group = dict(displayName="ZZZ_deleted_{time}_{orig}".format(time=time.time(), orig=group_name),
					 description="deleted group")
		core.modify_group(group_id=result_group["id"], group=group)


def timeout_error(**kwargs):
	# type: (Dict[str, Any]) -> None
	raise requests.exceptions.Timeout


def check_code_internal(response):
	# type: (Dict[str, Any]) -> Optional[Dict[str, Any]]
	if 300 > response["status"]["code"] >= 200:
		json_response = {} if len(response["body"]["string"]) == 0 else json.loads(gzip.decompress(response["body"]["string"]))

		# json_response = json.loads(gzip.decompress(response["body"]["string"]))
		if "status" not in json_response or ("status" in json_response and json_response["status"] == "succeeded"):
			return response
	return None


my_vcr = vcr.VCR(
	filter_headers=[('Authorization', 'XXXXXX')],
	before_record_response=check_code_internal,
)


class TestAzure:

	def setup(self):
		# type: () -> None
		""" """

		try:
			self.account = AzureAccount(alias=ALIASDOMAIN, config_base_path=DOMAIN_PATH)
		except FileNotFoundError as exc:
			print("FileNotFoundError: {exc}".format(exc=exc))
			pytest.exit(
				"FAIL: No testing files found in {} for domain {}. Skipping all tests".format(DOMAIN_PATH, ALIASDOMAIN))
		self.core = MSGraphApiCore(account=self.account)

	def test_completity(self):
		# type: () -> None
		diff = all_methods_called(self.__class__, MSGraphApiCore, ["response_to_values", "wait_for_operation"])
		assert len(diff) == 0, "Functions no tested [" + ", ".join(diff) + "]"

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_token.yml')
	def test_get_token(self):
		# type: () -> None
		"""
		It's been tested in every test setup.
		"""
		assert self.account.token.check_token()

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_token_fail_directory_id_not_exist.yml')
	def test_get_token_fail_directory_id_not_exist(self):
		# type: () -> None
		""" """
		with pytest.raises(MSGraphError):
			self.account["directory_id"] += "7"
			self.core.get_token()

	@patch.object(requests, 'request', mock.MagicMock(side_effect=timeout_error))
	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_token_fail_timeout.yml')
	def test_get_token_fail_timeout(self):
		# type: () -> None
		""" """
		with pytest.raises(requests.exceptions.Timeout):
			self.core.get_token()

	@pytest.mark.skip
	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_token_fail_client_assertion.yml')
	def test_get_token_fail_client_assertion(self):
		# type: () -> None
		""" """
		with pytest.raises(MSGraphError):
			self.core.get_token()

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_token_fail_application_id.yml')
	def test_get_token_fail_application_id(self):
		# type: () -> None
		""" """
		with pytest.raises(MSGraphError):
			self.account['application_id'] += "8"
			self.core.get_token()

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_token_fail_500.yml')
	def test_get_token_fail_500(self):
		# type: () -> None
		""" """
		with requests_mock.Mocker() as mock_request:
			mock_request.request(method='POST', url=URLs.ms_login(self.account["directory_id"]), text="Fail!", status_code=500)
			with pytest.raises(MSGraphError):
				self.core.get_token()

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_create_invitation.yml')
	def test_create_invitation(self):
		# type: () -> None
		"""
		None of the current applications have permissions to get an invitation
		We are currently only checking that it fails with the expected exception
		"""
		response = self.core.create_invitation("martinena@univention.de", "http://univention.de")
		assert "id" in response

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_azure_users.yml')
	def test_list_azure_users(self):
		# type: () -> None
		""" """
		self.core.list_azure_users(self.account["application_id"], paging=False)

	@pytest.mark.skip("/me request is only valid with delegated authentication flow.")
	def test_get_me(self):
		# type: () -> None
		""" """
		self.core.get_me()  # TODO: /me request is only valid with delegated authentication flow.

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_user.yml')
	def test_get_user(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_get_user") as user:
			self.core.get_user(user_id=user["id"])

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_create_group.yml')
	def test_create_group(self):
		# type: () -> None
		with new_group(self.core, "test_create_group") as group:
			print(group)
			pass

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_modify_group.yml')
	def test_modify_group(self):
		# type: () -> None
		with new_group(self.core, "test_modify_group") as group:
			print(group)
			new_description = "New description"
			self.core.modify_group(group["id"], dict(description=new_description))
			response = self.core.get_group(group["id"])
			assert response["description"] == new_description

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_delete_group.yml')
	def test_delete_group(self):
		# type: () -> None
		with new_group(self.core, "test_delete_group") as group:
			group_id = group["id"]
		response = self.core.get_group(group_id)
		assert "ZZZ_delete" in response["displayName"]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_group.yml')
	def test_get_group(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_get_group") as group:
			self.core.get_group(group["id"])

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_group_members.yml')
	def test_list_group_members(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_list_group_members") as user:
			with new_group(self.core, "test_list_group_members") as group:
				self.core.add_group_member(group["id"], user["id"])
				response = self.core.list_group_members(group["id"])
				assert user["id"] in [x["id"] for x in response["value"]]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_group_owners.yml')
	def test_list_group_owners(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_list_group_owners") as user:
			with new_group(self.core, "test_list_group_owners") as group:
				self.core.add_group_owner(group["id"], user["id"])
				response = self.core.list_group_owners(group["id"])
				assert user["id"] in [x["id"] for x in response["value"]]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_graph_users.yml')
	def test_list_graph_users(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_list_graph_users") as user:
			response = self.core.list_graph_users()
			assert user["id"] in [x["id"] for x in response["value"]]

	# @pytest.mark.skip
	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_team.yml')
	def test_get_team(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_get_team") as user:
			with new_team(self.core, "test_get_team", owner=user["id"]) as (team, group_id):
				time_slept = 0
				while True:
					try:
						self.core.get_team(group_id)
						break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_create_team.yml')
	def test_create_team(self):
		# type: () -> None
		"""
		The owner is hardcoded to d6aab5ff-9c88-4e45-9e0f-1321ee8fc8bd because the operation need a user with at least one valid license assigned.
		"""

		response = self.core.create_team("test_create_team", owner="d6aab5ff-9c88-4e45-9e0f-1321ee8fc8bd", description="Description test_create_team")
		team_id = response["Content-Location"].split("'")[1]
		time_slept = 0
		while True:
			try:
				self.core.delete_team(team_id)
				break
			except MSGraphError:
				time.sleep(10)
				time_slept += 10
				if time_slept >= 180:
					raise

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_add_group_owner.yml')
	def test_add_group_owner(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_add_group_owner") as user:
			with new_group(self.core, "test_add_group_owner") as group:
				self.core.add_group_owner(group["id"], user["id"])

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_add_group_member.yml')
	def test_add_group_member(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_add_group_member") as user:
			with new_group(self.core, "test_add_group_member") as group:
				self.core.add_group_member(group["id"], user["id"])

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_remove_group_member.yml')
	def test_remove_group_member(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_remove_group_member") as user:
			with new_group(self.core, "test_remove_group_member") as group:
				self.core.add_group_member(group["id"], user["id"])
				self.core.remove_group_member(group["id"], user["id"])

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_remove_group_owner.yml')
	def test_remove_group_owner(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_remove_group_owner") as user1:
			with new_user(self.core, "test_remove_group_owner2") as user2:
				with new_group(self.core, "test_remove_group_owner") as group:
					self.core.add_group_owner(group["id"], user1["id"])
					self.core.add_group_owner(group["id"], user2["id"])
					self.core.remove_group_owner(group["id"], user1["id"])

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_create_team_from_group.yml')
	def test_create_team_from_group(self):
		# type: () -> None
		"""
		Azure need to sync groups before converting it to a team
		"""
		with new_user(self.core, "test_create_team_from_group") as user1:
			with new_group(self.core, "test_create_team_from_group") as group:
				self.core.add_group_owner(group["id"], user1["id"])
				time_slept = 0
				while True:
					try:
						self.core.create_team_from_group(group["id"])
						break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise

	@pytest.mark.skip(
		"Never used in the previous implementation, Failed to retrieve applicable Sku categories for the user")
	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_create_team_from_group_current.yml')
	def test_create_team_from_group_current(self):
		# type: () -> None
		""" """
		# with new_user(self.core, "test_create_team_from_group_current") as user1:
		with new_group(self.core, "test_create_team_from_group_current") as group:
			self.core.add_group_owner(group["id"], "d6aab5ff-9c88-4e45-9e0f-1321ee8fc8bd")
			time_slept = 0
			while True:
				try:
					self.core.create_team_from_group_current(group["id"])
					break
				except MSGraphError:
					time.sleep(10)
					time_slept += 10
					if time_slept >= 180:
						raise

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_modify_team.yml')
	def test_modify_team(self):
		# type: () -> None
		team_name = "test_modify_team"
		with new_user(self.core, team_name) as result_user:
			with new_team(self.core, team_name, result_user["id"]) as (team, group_id):
				time_slept = 0
				while True:
					try:
						self.core.modify_team(group_id, dict(description="new_description of team_name"))
						break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise
				time_slept = 0
				while True:
					try:
						response = self.core.get_team(group_id)
						if "new_description of team_name" == response["description"]:
							break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_delete_team.yml')
	def test_delete_team(self):
		# type: () -> None
		""" """
		team_name = "test_add_team_member"
		with new_user(self.core, team_name) as result_user:
			with new_team(self.core, team_name, result_user["id"]) as (team, group_id):
				assert "request-id" in team

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_archive_team.yml')
	def test_archive_team(self):
		# type: () -> None
		""" """
		team_name = "test_add_team_member"
		with new_user(self.core, team_name) as result_user:
			with new_team(self.core, team_name, result_user["id"]) as (team, group_id):
				time_slept = 0
				while True:
					try:
						self.core.archive_team(group_id)
						break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise
				time_slept = 0
				while True:
					try:
						self.core.unarchive_team(group_id)

						break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_unarchive_team.yml')
	def test_unarchive_team(self):
		# type: () -> None
		""" """
		team_name = "test_add_team_member"
		with new_user(self.core, team_name) as result_user:
			with new_team(self.core, team_name, result_user["id"]) as (team, group_id):
				time_slept = 0
				while True:
					try:
						self.core.archive_team(group_id)
						break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise
				time_slept = 0
				while True:
					try:
						self.core.unarchive_team(group_id)

						break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_team_members.yml')
	def test_list_team_members(self):
		# type: () -> None
		""" """
		team_name = "test_add_team_member"
		with new_user(self.core, team_name) as result_user:
			with new_team(self.core, team_name, result_user["id"]) as (team, group_id):
				time_slept = 0
				while True:
					try:
						self.core.list_team_members(group_id)
						break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_add_team_member.yml')
	def test_add_team_member(self):
		# type: () -> None
		""" """
		team_name = "test_add_team_member"
		with new_user(self.core, team_name) as result_user:
			with new_team(self.core, team_name, result_user["id"]) as (team, group_id):
				time_slept = 0
				while True:
					try:
						self.core.add_team_member(group_id, result_user["id"])
						break
					except MSGraphError:
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_remove_team_member.yml')
	def test_remove_team_member(self):
		# type: () -> None
		""" """
		team_name = "test_remove_team_member"
		with new_user(self.core, team_name) as result_user1:
			with new_user(self.core, team_name + "2") as result_user2:
				with new_team(self.core, team_name, result_user1["id"]) as (team, group_id):
					time_slept = 0
					while True:
						try:
							response = self.core.add_team_member(group_id, result_user2["id"])
							break
						except MSGraphError as e:
							time.sleep(10)
							time_slept += 10
							if time_slept >= 180:
								raise e
					time_slept = 0
					while True:
						try:
							self.core.remove_team_member(group_id, response["id"])
							break
						except MSGraphError:
							time.sleep(10)
							time_slept += 10
							if time_slept >= 500:
								raise
					time_slept = 0
					while True:
						response = self.core.list_group_members(group_id=group_id)
						if result_user2["id"] not in [x["id"] for x in response["value"]]:
							break
						time.sleep(10)
						time_slept += 10
						if time_slept >= 180:
							raise Exception("User not deleted from azure, but operation return the expected code")

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_add_user.yml')
	def test_add_user(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_add_user") as result_user:
			assert "id" in result_user

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_add_simple_user.yml')
	def test_add_simple_user(self):
		# type: () -> None
		""" """
		username = "user_{team_name}".format(team_name="test_add_simple_user")
		user_email = "{username}@{domain}".format(username=username, domain=DOMAIN)
		result_user = self.core.add_simple_user(username=username, email=user_email, password="1*#" + "".join(random.choices(string.ascii_letters, k=10)))
		user = dict(accountEnabled=False, userPrincipalName="ZZZ_deleted_{time}_{orig}".format(time=time.time(), orig=user_email), displayName="ZZZ_deleted_{time}_{orig}".format(time=time.time(), orig=username))
		self.core.modify_user(oid=result_user["id"], user=user)

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_delete_user.yml')
	def test_delete_user(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_delete_user") as result_user:
			assert "id" in result_user

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_modify_user.yml')
	def test_modify_user(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_user") as result_user:
			assert "id" in result_user
			self.core.modify_user(result_user["id"], {"postalCode": "10004"})

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_member_of.yml')
	def test_member_of(self):
		# type: () -> None
		""" """
		with new_user(self.core, "test_user") as user:
			with new_group(self.core, "test_user") as group:
				self.core.add_group_member(group["id"], user["id"])
				result = self.core.member_of(user["id"])
				assert group["id"] in [x["id"] for x in result["value"]]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_test_list_team.yml')
	def test_test_list_team(self):
		# type: () -> None
		""" """
		self.core.test_list_team()

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_teams.yml')
	def test_list_teams(self):
		# type: () -> None
		""" """
		self.core.list_teams(paging=False)

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_member_of_objects.yml')
	def test_member_of_objects(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_member_of_objects") as group:
			with new_user(self.core, "test_member_of_objects") as user:
				self.core.add_group_member(group["id"], user["id"])
				result = self.core.member_of_objects(object_id=user["id"])
				assert group["id"] in [x for x in result["value"]]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_add_license.yml')
	def test_add_license(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_add_license") as user:
			licenses = self.core.list_subscriptions()
			self.core.add_license(user["id"], sku_id=licenses["value"][0]["skuId"])
			self.core.remove_license(user["id"], sku_id=licenses["value"][0]["skuId"])

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_domains.yml')
	def test_list_domains(self):
		# type: () -> None
		""""""
		domains = self.core.list_domains()
		assert "value" in domains

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_subscriptions.yml')
	def test_list_subscriptions(self):
		# type: () -> None
		""""""
		subscriptions = self.core.list_subscriptions()
		assert "value" in subscriptions

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_users.yml')
	def test_list_users(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_list_users") as user:
			users = self.core.list_users()
			assert user["id"] in [x["id"] for x in users["value"]]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_member_of_groups.yml')
	def test_member_of_groups(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_member_of_groups") as group:
			with new_user(self.core, "test_member_of_groups") as user:
				self.core.add_group_member(group["id"], user["id"])
				members = self.core.member_of_groups(user["id"])
				assert group["id"] in [x for x in members["value"]]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_resolve_object_ids.yml')
	def test_resolve_object_ids(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_resolve_object_ids") as user:
			user_obj = self.core.resolve_object_ids([user["id"]])
			assert user_obj["value"][0]["id"] == user["id"]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_invalidate_all_tokens_for_user.yml')
	def test_invalidate_all_tokens_for_user(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_invalidate_tokens") as user:
			result = self.core.invalidate_all_tokens_for_user(user["id"])
			assert '@odata.context' in result

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_add_group_members.yml')
	def test_add_group_members(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_add_group_members") as group:
			with new_user(self.core, "test_add_group_members") as user1:
				with new_user(self.core, "test_add_group_members2") as user2:
					self.core.add_group_members(group["id"], [user1["id"], user2["id"]])
					members = self.core.list_group_members(group["id"])
					assert user1["id"] in [x["id"] for x in members["value"]]
					assert user2["id"] in [x["id"] for x in members["value"]]
					self.core.remove_group_member(group["id"], user1["id"])
					self.core.remove_group_member(group["id"], user2["id"])

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_verified_domains.yml')
	def test_list_verified_domains(self):
		# type: () -> None
		""""""
		verified_domains = self.core.list_verified_domains()
		assert "value" in verified_domains

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_groups.yml')
	def test_list_groups(self):
		# type: () -> None
		""""""
		with new_group(self.core, "test_list_groups") as group:
			groups = self.core.list_groups()
			assert group["id"] in [x["id"] for x in groups["value"]]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_list_groups_by_displayname.yml')
	def test_list_groups_by_displayname(self):
		# type: () -> None
		with new_group(self.core, "test_list_groups_by_disName") as group:
			groups = self.core.list_groups_by_displayname(name=group["displayName"])
			assert group["id"] in [x["id"] for x in groups["value"]]

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_remove_license.yml')
	def test_remove_license(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_remove_license") as user:
			licenses = self.core.list_subscriptions()
			self.core.add_license(user["id"], sku_id=licenses["value"][0]["skuId"])
			self.core.remove_license(user["id"], sku_id=licenses["value"][0]["skuId"])

	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_get_subscriptionSku.yml')
	def test_get_subscriptionSku(self):
		# type: () -> None
		""""""
		test_default_id = "3e7d9eb5-c3a1-4cfc-892e-a8ec29e45b77_6fd2c87f-b296-42f0-b197-1e91e994b900"
		response = self.core.get_subscriptionSku(test_default_id)
		assert test_default_id == response["id"]

	@pytest.mark.skip
	@my_vcr.use_cassette('vcr_cassettes/TestAzure/test_change_password.yml')
	def test_change_password(self):
		# type: () -> None
		""""""
		with new_user(self.core, "test_remove_license") as user:
			self.core.change_password(user["id"], user["passwordProfile"]["password"], create_random_pw())
