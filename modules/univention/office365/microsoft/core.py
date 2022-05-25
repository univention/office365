import json
from typing import Dict, List, Union
from six.moves.urllib.parse import quote

import requests

from univention.office365.microsoft.exceptions.core_exceptions import MSGraphError, exception_decorator
from univention.office365.microsoft.account import AzureAccount
from univention.office365.microsoft.urls import URLs
from univention.office365.logging2udebug import get_logger

logger = get_logger("office365", "core")


class MSGraphApiCore:
	"""
	This class is the core of the MSGraph API.
	Most of the methods are wrappers around the requests to the MSGraph API.
	Attributes:
		- account: The AzureAccount object with the credentials to access the MSGraph API.
	Methods
		- _call_graph_api is the main method to call the MSGraph API and process and control the response.

	"""
	# TODO: Check if response_handlers is used in any other place
	def __init__(self, account, response_handlers=None):
		# type: (AzureAccount, Dict) -> None
		response_handlers = response_handlers or {}
		self.account = account
		if not account.check_token():
			self.get_token(
				response_handlers=response_handlers
				# response_handlers={504: self._handler_for_504, 400: self._handler_for_504}  #  TODO: implement handlers
			)
			# Save token

	def get_token(self, response_handlers=None):
		# type: (Dict) -> None
		"""
		Get an access token for the given directory id and application id.
		COMPATIBLITY NOTE / CHANGES BETWEEN 'Graph' AND 'Azure'

		With minor adjustments this function has also been able to get a token
		from azure with the following endpoint:
			endpoint = "https://login.microsoftonline.com/{directory_id}/oauth2/token".format(
				directory_id=token_file_as_json['directory_id']
			)

		with the new graph endpoint the directory_id becomes optional, source:
		https://docs.microsoft.com/en-us/graph/migrate-azure-ad-graph-request-differences#basic-requests

		the 'scope' parameter has to be adjusted in order to use Azure
		"""
		self.account.renewing = True
		endpoint = URLs.ms_login(self.account["directory_id"])

		response = self._call_graph_api(
			'POST',
			endpoint,
			headers={'Content-Type': 'application/x-www-form-urlencoded'},
			data={  # NOTE do not use json.dumps here, because this is a different content-type!
				'client_id': self.account['application_id'],
				'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
				'client_assertion': self.account.client_assertion(),
				'grant_type': 'client_credentials',
				'scope': ['https://graph.microsoft.com/.default']
			},
			expected_status=[200],
			retry=0,
			response_handlers=response_handlers
		)
		self.account.update_and_save_token(response)
		self.account.renewing = False

	def create_invitation(self, invitedUserEmailAddress, inviteRedirectUrl):
		# type: (str, str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/invitation-post
			returns: a user object of type `Guest`
		"""

		return self._call_graph_api(
			method='POST',
			url=URLs.invitations(),
			data=json.dumps(dict(
				{
					'invitedUserEmailAddress': quote(invitedUserEmailAddress, safe='@'),
					'inviteRedirectUrl': quote(inviteRedirectUrl, safe=':/')
				}
			)),
			headers={'Content-Type': 'application/json'},
			expected_status=[201]
		)

	def list_azure_users(self, application_id, paging=True):
		# type: (str, bool) -> Dict
		"""
			NOTE: This function should only be used for testing!
			This function calls the Azure API with a Graph access token.
			According to the documentation it should be doable somehow. As we
			do not need this function at the moment, it is kept here as a
			reminder and possible starting point if that becomes relevant in
			the future, when we start implementing backwards compatibility.
		"""
		return self._call_graph_api(
			method='GET',
			url=URLs.users(),
			expected_status=[200],
			page=paging
		)

	def list_graph_users(self):
		# type: () -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/user-list
		"""

		return self._call_graph_api(
			'GET',
			URLs.users(),
			expected_status=[200]
		)

	def get_me(self):
		# type: () -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/user-get
		"""

		return self._call_graph_api(
			'GET',
			URLs.me(),
			expected_status=[200]
		)

	def get_user(self, user_id, selection=None):
		# type: (str, str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/user-get
		"""
		selection = "$select=" + selection if selection and selection is not "" else None
		return self._call_graph_api(
			'GET',
			URLs.users(path=user_id, params=selection),
			expected_status=[200]
		)

	def get_group(self, group_id, selection=None):
		# type: (str, str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/user-get
		"""

		selection = "$select=" + selection if selection and selection is not "" else None
		return self._call_graph_api(
			'GET',
			URLs.groups(params=selection, path=group_id),
			expected_status=[200]
		)

	def get_team(self, group_id):
		# type: (str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/team-get

		If the group was created less than 15 minutes ago, it's possible for the Create team call to fail with a 404 error code due to replication delays. The recommended pattern is to retry the Create team call three times, with a 10 second delay between calls.
		https://docs.microsoft.com/en-us/graph/api/team-put-teams
		"""

		return self._call_graph_api(
			'GET',
			URLs.teams(path=group_id),
			expected_status=[200]
		)

	def wait_for_operation(self, location):
		# type: (str) -> Dict
		return self._call_graph_api(
			'GET',
			URLs.base() + location,
			expected_status=[200]
		)

	def create_team(self, name, owner, description=""):
		# type: (str, str, str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/team-post
			we can't use create_team because the owner needs a valid license for MS Teams
       		instead use create_team_from_group
		"""
		return self._call_graph_api(
			'POST',
			URLs.teams(),
			data=json.dumps(
				{
					'template@odata.bind': "https://graph.microsoft.com/v1.0/teamsTemplates('standard')",
					'displayName': name,
					'description': description,
					"members": [
						{
							"@odata.type": "#microsoft.graph.aadUserConversationMember",
							"roles": ["owner"],
							"user@odata.bind": "https://graph.microsoft.com/v1.0/users('{userid}')".format(userid=owner)
						}
					]
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[
				202,  # Team is created asynchronously in Azure
				409   # Group already is a team - nothing to do
			]
		)

	def add_group_owner(self, group_id, owner_id):
		# type: (str, str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/group-post-owners
		"""

		return self._call_graph_api(
			'POST',
			URLs.groups(path='{group_id}/owners/$ref'.format(
				group_id=group_id
			)),
			data=json.dumps(
				{
					"@odata.id": "https://graph.microsoft.com/v1.0/users/{owner_id}".format(
						owner_id=owner_id
					)
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[
				204,  # 204 means success and has an empty content body according to MS
				400   # 400 means, that the user already been added.
			]
		)

	def remove_group_owner(self, group_id, owner_id):
		# type: (str, str) -> Dict
		""" https://hutten.knut.univention.de/mediawiki/index.php/Security_Updates
		Once owners are assigned to a group, the last owner of the group cannot be removed.
		"""

		return self._call_graph_api(
			'DELETE',
			URLs.groups(path='{group_id}/owners/{owner_id}/$ref'.format(
				group_id=group_id, owner_id=owner_id
			)),
			expected_status=[
				204,  # 204 means success and has an empty content body according to MS
			]
		)

	def create_team_from_group(self, object_id):
		# type: (str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/team-put-teams

			Create a new team under a group.
			If the group was created less than 15 minutes ago, it's possible for the Create team call to fail
			with a 404 error code due to replication delays. The recommended pattern is to retry the Create team
			call three times, with a 10 second delay between calls.
		"""

		return self._call_graph_api(
			'POST',
			URLs.teams(),
			data=json.dumps({
				"template@odata.bind":
					"https://graph.microsoft.com/v1.0/teamsTemplates('standard')",

				"group@odata.bind":
					"https://graph.microsoft.com/v1.0/groups('{object_id}')".format(
						object_id=object_id
					)
			}),
			headers={'Content-Type': 'application/json'},
			expected_status=[
				201,  # the documented success value is never returned in tests
				202   # instead there is 202 if it works
			]
		)

	def create_team_from_group_current(self, object_id):  # object_id is similar to cb57b853-be97-457c-8232-491dd82f5940
		# type: (str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/team-put-teams

			Here is the non-beta endpont version of the create_team_from_group
			function with limited functionality. It does e.g. not work with
			"Cannot migrate this group, id:
			364ff58b-b67a-4a74-8f6d-ac3e9ff7db38, access type: [...]
		"""

		return self._call_graph_api(
			'PUT',
			URLs.groups(path='{object_id}/team'.format(object_id=object_id)),
			data=json.dumps(
				{
					"memberSettings": {
						"allowCreatePrivateChannels": True,
						"allowCreateUpdateChannels": True
					},
					"messagingSettings": {
						"allowUserEditMessages": True,
						"allowUserDeleteMessages": True
					},
					"funSettings": {
						"allowGiphy": True,
						"giphyContentRating": "strict"
					}
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[201]
		)

	def modify_team(self, team_id, team):
		# type: (str, Dict) -> Dict
		return self._call_graph_api(
			'PATCH',
			URLs.teams(path=team_id),
			data=json.dumps(team),
			headers={'Content-Type': 'application/json'},
			expected_status=[204]
		)

	def delete_team(self, group_id):
		# type: (str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/group-delete

			NOTE
			----

			It was considered to use the delete_group function from the base
			class, but the function does currently not delete groups.  Instead
			it renames them. The implementation of this function was thus added
			as a requirement to clean up after each test execution.

			WARNING
			-------

			Be careful though, because this function can now be used to delete
			teams as well as groups and that was successfully tested. An
			additional application permission is necessary: Group.ReadWrite.All
		"""

		return self._call_graph_api(
			'DELETE',
			URLs.groups(path='{group_id}'.format(group_id=group_id)),
			expected_status=[204],
			data=json.dumps({})
		)

	def archive_team(self, team_id):
		# type: (str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/team-archive

			This function sets a team `inactive`.

			NOTE
			----
			The `shouldSetSpoSiteReadOnlyForMembers` parameter is not supported
			in the application context.

			RAISES
			------
			GraphError if unsuccessful

			RETURNS
			-------
			Nothing if successful.
		"""

		return self._call_graph_api(
			'POST',
			URLs.teams(path='{team_id}/archive'.format(team_id=team_id)),
			headers={'Content-Type': 'application/json'},
			data=json.dumps({"shouldSetSpoSiteReadOnlyForMembers": False}),
			expected_status=[202]
		)

	def unarchive_team(self, team_id):
		# type: (str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/team-unarchive

			This function reactivates a team.

			RETURNS
			-------
			A http header with the `Location` of the restored team
		"""

		return self._call_graph_api(
			'POST',
			URLs.teams(path='{team_id}/unarchive'.format(team_id=team_id)),
			expected_status=[202]
		)

	def list_team_members(self, team_id):
		# type: (str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/team-list-members
		"""

		return self._call_graph_api(
			'GET',
			URLs.teams(path='{team_id}/members'.format(team_id=team_id)),
			expected_status=[200]
		)

	def add_team_member(self, team_id, user_id):
		# type: (str, str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/team-post-members

			PERMISSIONS
			-----------
			Application
				TeamMember.ReadWrite.All
		"""

		return self._call_graph_api(
			'POST',
			URLs.teams(path='{object_id}/members'.format(object_id=team_id)),
			data=json.dumps(
				{
					"@odata.type": "#microsoft.graph.aadUserConversationMember",
					"user@odata.bind": "https://graph.microsoft.com/v1.0/users('{user_id}')".format(user_id=user_id)
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[201]
		)

	def add_group_member(self, group_id, object_id):
		# type: (str, str) -> Dict
		"""
		https://docs.microsoft.com/en-us/graph/api/resources/teams-api-overview?view=graph-rest-1.0
		"To add members and owners to a team, change the membership of the group with the same ID."

		https://docs.microsoft.com/en-us/graph/api/group-post-members?view=graph-rest-1.0&tabs=http

		:param group_id: azure object id of group object
		:param object_id: azure object id of user or group object to add to the group
		:return: 2xx if okay, 400 if user already is member, 404 if object to be added does not exist
		"""

		return self._call_graph_api(
			'POST',
			URLs.groups(path='{group_id}/members/$ref'.format(group_id=group_id)),
			data=json.dumps(
				{
					"@odata.id":
						"https://graph.microsoft.com/v1.0/directoryObjects/{object_id}".format(
							object_id=object_id)
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[204]
		)

	def add_group_members(self, group_id, object_ids):
		# type: (str, List) -> None
		"""
		https://docs.microsoft.com/en-us/graph/api/resources/teams-api-overview?view=graph-rest-1.0
		"To add members and owners to a team, change the membership of the group with the same ID."

		https://docs.microsoft.com/en-us/graph/api/group-post-members?view=graph-rest-1.0&tabs=http

		:param group_id: azure object id of group object
		:param object_ids: azure object id of user or group object to add to the group
		:return: 2xx if okay, 400 if user already is member, 404 if object to be added does not exist
		"""
		# We work with a batch of 20 objects because MS Graph API has limited it.
		assert isinstance(object_ids, (list, tuple, set))

		# remove from list object_ids already added.
		object_ids = set(object_ids)
		object_ids = object_ids - set([x["id"] for x in self.list_group_members(group_id)["value"]])
		object_ids = list(object_ids)

		for i in range(0, len(object_ids), 20):
			batch = object_ids[i:min(i+20, len(object_ids))]

			self._call_graph_api(
				'PATCH',
				URLs.groups(path='{group_id}'.format(group_id=group_id)),
				data=json.dumps(
					{
						"members@odata.bind": [ "https://graph.microsoft.com/v1.0/directoryObjects/{object_id}".format(
								object_id=oid) for oid in batch]
					}
				),
				headers={'Content-Type': 'application/json'},
				expected_status=[204]
			)

	def remove_group_member(self, group_id, object_id):
		# type: (str, str) -> Dict
		"""
		https://docs.microsoft.com/en-us/graph/api/resources/teams-api-overview?view=graph-rest-1.0
		"To add/remove members and owners to a team, change the membership of the group with the same ID."

		https://docs.microsoft.com/en-us/graph/api/group-delete-members?view=graph-rest-1.0&tabs=http
		:param group_id: azure object id of group object
		:param object_id: azure object id of user object to remove from the group
		:return: 204 no content
		"""
		return self._call_graph_api(
			'DELETE',
			URLs.groups(path='{group_id}/members/{object_id}/$ref'.format(
				group_id=group_id,
				object_id=object_id
				)
			),
			expected_status=[204]
		)

	def remove_team_member(self, team_id, membership_id):
		# type: (str, str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/team-post-members

			PERMISSIONS
			-----------
			Application
				User.ReadWrite.All
		"""

		return self._call_graph_api(
			'DELETE',
			URLs.teams(path='{team_id}/members/{membership_id}'.format(
				team_id=team_id,
				membership_id=membership_id)
			),
			expected_status=[204]
		)

	def add_simple_user(self, username, email, password):
		# type: (str, str, str) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/user-post-users
		"""

		return self._call_graph_api(
			'POST',
			URLs.users(),
			data=json.dumps({
				"accountEnabled": True,
				"displayName": username,
				"mailNickname": username,
				"userPrincipalName": email,
				"passwordProfile": {
					"forceChangePasswordNextSignIn": True,
					"password": password
				}
			}),
			headers={'Content-Type': 'application/json'},
			expected_status=[201]
		)

	def add_user(self, attr):
		# type: (Dict) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/user-post-users
		"""

		return self._call_graph_api(
			'POST',
			URLs.users(),
			data=json.dumps(attr),
			headers={'Content-Type': 'application/json'},
			expected_status=[201]
		)

	def delete_user(self, oid):
		# type: (str) -> Dict
		"""https://docs.microsoft.com/en-us/graph/api/user-delete?view=graph-rest-1.0&tabs=http
		The connection should be configured to set privileges to delete users.
		"""
		return self._call_graph_api(
			'DELETE',
			URLs.users(path=oid),
			data=json.dumps({}),
			expected_status=[204]
		)

	def modify_user(self, oid, user):
		# type: (str, Dict) -> Dict
		"""
		https://docs.microsoft.com/en-us/graph/api/user-update?view=graph-rest-1.0&tabs=http
		"""
		return self._call_graph_api(
			'PATCH',
			URLs.users(path=oid),
			data=json.dumps(user),
			headers={'Content-Type': 'application/json'},
			expected_status=[204]
		)

	def member_of(self, object_id):  # TODO añadir bool para listar todos los objetos
		# type: (str) -> Dict
		""""""
		return self._call_graph_api(
			'GET',
			URLs.directory_objects(path=object_id+"/memberOf"),
			expected_status=[200]
		)

	def member_of_objects(self, object_id):
		# type: (str) -> Dict
		""""""
		return self._call_graph_api(
			'POST',
			URLs.directory_objects(path="{object_id}/getMemberObjects".format(object_id=object_id)),
			data=json.dumps({"securityEnabledOnly": False}),
			headers={'Content-Type': 'application/json'},
			expected_status=[200]
		)

	def member_of_groups(self, object_id):
		# type: (str) -> Dict
		""""""
		return self._call_graph_api(
			'POST',
			URLs.directory_objects(path="{object_id}/getMemberGroups".format(object_id=object_id)),
			data=json.dumps({"securityEnabledOnly": False}),
			headers={'Content-Type': 'application/json'},
			expected_status=[200]
		)

	def create_group(self, data):
		# type: (Dict) -> Dict
		return self._call_graph_api(
			'POST',
			URLs.groups(),
			data=json.dumps(data),
			expected_status=[201],
			headers={'Content-Type': 'application/json'}
		)

	def modify_group(self, group_id, group):
		# type: (str, Dict) -> Dict
		return self._call_graph_api(
			'PATCH',
			URLs.groups(path=group_id),
			data=json.dumps(group),
			headers={'Content-Type': 'application/json'},
			expected_status=[204]
		)

	def delete_group(self, group_id):
		# type: (str) -> Dict
		return self._call_graph_api(
			'DELETE',
			URLs.groups(path=group_id),
			data=json.dumps({}),
			expected_status=[204]
		)

	def list_group_members(self, group_id, links= False, filter=None):  # TODO añadir bool para sacar los enlaces
		# type: (str, bool, Optional[str]) -> Dict
		"""
		Get members of a group (data)
		:param group_id:
		:param links:
		:return:
		"""
		ref = "/$ref" if links else ""
		return self._call_graph_api(
			'GET',
			URLs.groups(path=group_id + "/members" + ref, params=filter),
			expected_status=[200]
		)

	def list_group_owners(self, group_id):
		# type: (str) -> Dict
		return self._call_graph_api(
			'GET',
			URLs.groups(path=group_id + "/owners"),
			expected_status=[200]
		)

	def test_list_team(self):
		# type: () -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/group-list

			Summary
			This function has the purpose to determine
			if the team functionality has the correct permissions
			set. This is called in the office365-group.py listener
			module.
		"""

		return self._call_graph_api(
			'GET',
			URLs.groups('$count'),
			expected_status=[200],
			page=False
		)

	def list_teams(self, paging=True):
		# type: (bool) -> Dict
		""" https://docs.microsoft.com/en-us/graph/api/group-list

			Summary
			-------

			this is a simplification which we should try to keep up to date
			with the API. This function could potentially return a very long
			array and its performance can be tuned with the `$top` parameter
			in the future, which allows pagination with more items per page
			and a maximum of 999 at the time of writing this comment. More
			info here: https://docs.microsoft.com/en-us/graph/paging
		"""

		return self._call_graph_api(
			'GET',
			URLs.groups("$filter=resourceProvisioningOptions/Any(x:x eq 'Team')&$select=id"),
			expected_status=[200],
			page=paging
		)

	@exception_decorator
	def _call_graph_api(self, method, url, data=None, retry=3, headers=None, expected_status=None, page=True, response_handlers=None):
		# type: (str, str, Union[str, Dict], int, Dict, List, bool, Dict) -> Dict
		""" SUMMARY
			-------

			private function to avoid code duplication and make all calls
			generic. It adds support for pagination, proxy handling and
			automatic retries after different server errors, if necessary.

			ATTRIBUTES
			----------

			method : str
				GET|POST|PATCH|PUT|DELETE|...

			url : str
				string in the form protocol://tld.example.com/path/[file]?params

			data : dict
				a json-object or dict to be used as payload

			RAISES
			------

			GraphError
				A gerneric error with all necessary information for debugging.
				All erros returned by this function have use the (private)
				_generate_error_message function to format the error message
				in a readable way.

			RETURNS
			-------

			a Dict with the return values from the Microsoft server
		"""
		headers = headers or {}
		expected_status = expected_status or []
		assert len(expected_status) > 0, "expected_status is required"
		response_handlers = response_handlers or {}
		values = {}  # holds data from pagination
		msg = MSGraphApiCore._fprints_hide_pw(data, "GraphAPI: {method} {url}".format(method=method, url=url))
		logger.debug(msg)

		# prepare the http headers, which we are going to send with any request
		# the access_token should have been initialized in the constructor.
		# if not we still continue, because that allows us to use this function
		# for the acquisition of the access token as well.
		headers.update({'User-Agent': 'Univention Microsoft 365 Connector'})


		# TODO: do try except better with a retry counter
		# TODO: URLs.proxies must use UCR
		timeout = False
		while url != "":
			if hasattr(self, "account") and not self.account.renewing:
				if not self.account.check_token():
					self.get_token()  #TODO implement handlers
				headers.update({'Authorization': 'Bearer {}'.format(self.account.token['access_token'])})
			try:
				response = requests.request(
					method=method,
					url=url,
					verify=True,
					headers=headers,
					data=data,
					proxies=URLs.proxies(logger=logger),
					timeout=10
				)
			except requests.exceptions.Timeout:
				if not timeout:
					timeout = True
					continue
				raise

			logger.info(
				"status: %r (%s) (%s %s)",
				response.status_code,
				"OK" if 200 <= response.status_code <= 299 else "FAIL",
				method.upper(),
				url)

			# call handlers for response
			if response.status_code in response_handlers.keys():
				response_handlers[response.status_code](response, retry)

			if response.status_code not in expected_status:
				raise MSGraphError(response, expected_status=expected_status)
			values, url = MSGraphApiCore.response_to_values(response, page, values, expected_status)
		return values

	@staticmethod
	def response_to_values(response, page, values, expected_status):
		# type: (requests.Response, bool, Dict, List) -> (Dict, str)
		if not response.content:
			# an empty response is usually not an error and if the relevant
			# data are not in the body, they can usually be found in the
			# reponse headers...
			return dict(response.headers), ""
		else:
			try:
				response_json = response.json()

				if 'value' in values:
					values['value'].extend(response_json['value'])
				else:
					values = response_json

				if not (page and ('@odata.nextLink' in response_json)):
					# explicitly break the loop, because we are done
					return values, ""
				else:
					# implement pagination: as long as further pages follow, we
					# want to request these and as long as url is set, this loop
					# will append to the `values` array
					url = response_json.get("@odata.nextLink")
					logger.debug('Next page: {url}'.format(url=url))
					return values, url

			except ValueError as exc:
				raise MSGraphError(
					response,
					"Response payload was not parseable by the json parser: {error}".format(
						error=str(exc)
					),
					expected_status
				)

	# TODO: move to an util class/file
	# TODO: make the method parameterizable
	@staticmethod
	def _fprints_hide_pw(data, msg):
		# type: (Dict, str) -> str
		"""
		Create string for logging without password.

		:param data: dict to print in {data}, data["passwordProfile"]["password"] will be replaced with "******"
		:param msg: string containing {data}
		:return: msg formatted
		"""
		tmppw = None
		if isinstance(data, dict) and "passwordProfile" in data and "password" in data["passwordProfile"]:
			tmppw = data["passwordProfile"]["password"]
			data["passwordProfile"]["password"] = "******"
		msg = msg.format(data=data)
		if tmppw:
			data["passwordProfile"]["password"] = tmppw
		return msg

	def list_subscriptions(self):
		# type: () -> Dict
		"""
		Get subscriptions of User,Rol,Group, Team
		"""
		return self._call_graph_api('GET', URLs.subscription(), expected_status=[200], page=True)

	def invalidate_all_tokens_for_user(self, user_id):
		# type: (str) -> Dict
		""""""
		# params = urlencode(azure_params)
		# url = self.uris["invalidateTokens"].format(user_id=user_id, params=params)
		# return self.call_api("POST", url)
		return self._call_graph_api('POST', URLs.users(path="{user_id}/invalidateAllRefreshTokens".format(user_id=user_id)), expected_status=[200], headers={'Content-Type': 'application/json'}, data=json.dumps({}))

	def list_domains(self):
		# type: () -> Dict
		"""List all domains"""
		return self._call_graph_api('GET',
			URLs.domains(),
			expected_status=[200],
			page=True
		)

	def list_groups(self, params=""):
		# type: (str) -> Dict
		"""List all groups"""
		return self._call_graph_api('GET', URLs.groups(params=params), expected_status=[200], page=True)

	def list_groups_by_displayname(self, name):
		# type: (str) -> Dict
		"""List all groups"""
		return self.list_groups(params="?$filter=displayName eq '{}'".format(name))

	def list_users(self):
		# type: () -> Dict
		"""List all users"""
		return self._call_graph_api('GET', URLs.users(), expected_status=[200], page=True)

	def list_verified_domains(self):
		# type: () -> Dict
		"""
				Verified domains - only those can be used for userPrincipalName!
				Use get_verified_domain_from_disk() for user creation.
				"""
		domains = self.list_domains()
		domains["value"] = [domain for domain in domains["value"] if domain["isVerified"]]
		return domains

	def add_license(self, user_id, sku_id, deactivate_plans=None):
		# type: (str, str, List) -> Dict
		"""Add license to user_id"""
		assert isinstance(sku_id, str)
		assert isinstance(deactivate_plans, list) or deactivate_plans is None
		deactivate_plans = deactivate_plans or []

		return self._call_graph_api('POST',
			URLs.users(path="{user_id}/assignLicense".format(user_id=user_id)),
			data=json.dumps(
				{
					"addLicenses": [
						{
							"disabledPlans": deactivate_plans,
							"skuId": sku_id
						}
					],
					"removeLicenses": []
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[200],
		)

	def remove_license(self, user_id, sku_id):
		# type: (str, str) -> Dict
		"""Remove license from user_id"""
		assert isinstance(sku_id, str)

		return self._call_graph_api('POST',
			URLs.users(path="{user_id}/assignLicense".format(user_id=user_id)),
			data=json.dumps(
				{
					"addLicenses": [],
					"removeLicenses": [sku_id]
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[200],
		)

	def resolve_object_ids(self, object_ids):
		# type: (List) -> Dict
		"""Resolve object from objects_ids"""
		assert isinstance(object_ids, list)
		object_ids = list(set(object_ids))

		return self._call_graph_api('POST',
			URLs.directory_objects(path="getByIds"),
			data=json.dumps(
				{
					"ids": object_ids,
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[200],
		)

	def change_password(self, user_id, old_pw, new_pw):
		# type: (str, str, str) -> Dict
		return self._call_graph_api('POST',
			URLs.users(path="{user_id}/changePassword".format(user_id=user_id)),
			data=json.dumps(
				{
					"currentPassword": old_pw,
					"newPassword": new_pw
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[200],
		)

	def get_subscriptionSku(self, subs_sku_id):
		# type: (str) -> Dict
		return self._call_graph_api('GET',
			URLs.subscription(path="{subs_sku_id}".format(subs_sku_id=subs_sku_id)),
			expected_status=[200],
		)
		pass