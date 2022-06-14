import datetime
import json
import requests
import time

from six.moves.urllib.parse import quote

import os
import grp
import pwd
import shutil

from univention.office365.api.exceptions import GraphError
from univention.office365.certificate_helper import get_client_assertion_from_alias, load_ids_file
from univention.office365.api_helper import get_http_proxies
from univention.office365.azure_handler import AzureHandler
from univention.office365.logging2udebug import get_logger
from univention.office365.api_helper import write_async_job

logger = get_logger("office365", "o365")

'''
	The Graph class is kept compatible with the former `azure_handler.py` class and
	can be used as a drop-in-replacement for it. It still relies on the
	AzureHandlers functionality and acts as a compatibility layer, while it
	simultaneously allows the incremental reimplementation of functions on top of
	it, or in other words 'overwrite functions' until all calls have been migrated,
	then remove the base class `AzureHandler`.

	One main idea in this class is, that there is only one http code for a
	successful call and many different error values. The first check after each API
	call is therefore a check for a successful return code and that can be found
	in the Microsoft documentation under `Response` for each endpoint.
'''

uid = pwd.getpwnam("listener").pw_uid
gid = grp.getgrnam("nogroup").gr_gid


class Graph(AzureHandler):

	# ==========================================================================
	# initalization

	def __init__(self, ucr, name, connection_alias, logger=logger):
		''' constructor; signature compatible with azure_handler
			:param ucr: an initialized instance of the univention config registry
			:param name:  an arbitrary name which will appear in all error messages
			:param connection_alias: a connection configuration from /etc/univention-office365/
			:param logger: (optional) an initialized logger
		'''
		self.name = name
		self.connection_alias = connection_alias
		self.logger = logger

		# proxies must be set before any attempt to call the API
		self.proxies = get_http_proxies(ucr, self.logger)
		self.access_token_json = self._login(connection_alias)

		# We also initialize the base class, so that it becomes usable...
		super(Graph, self).__init__(ucr, name, connection_alias)
		# we expect the baseclass to set 'auth'. If the implementation ever
		# changes we will be warned.
		if (not hasattr(self, 'auth')):  # TODO at some point: remove this code
			self.logger.warn(
				"Implementation changed!"
				"The base class initialisation did not set self.auth."
				"Trying to fix that problem by adding necessary values."
			)

	# ==========================================================================
	# login logics

	def _login(self, connection_alias, force_new_token=False):
		'''
			COMPATIBLITY NOTE / CHANGES BETWEEN 'Graph' AND 'Azure'

			With minor adjustments this function has also been able to get a token
			from azure with the following endpoint:
				endpoint = "https://login.microsoftonline.com/{directory_id}/oauth2/token".format(
					directory_id=token_file_as_json['directory_id']
				)

			with the new graph endpoint the directory_id becomes optional, source:
			https://docs.microsoft.com/en-us/graph/migrate-azure-ad-graph-request-differences#basic-requests

			the 'scope' parameter has to be adjusted in order to use Azure
		'''
		fn_access_token_cache_tmp = "/etc/univention-office365/{alias}/access_token_graph.json.tmp".format(
			alias=connection_alias
		)
		fn_access_token_cache = "/etc/univention-office365/{alias}/access_token_graph.json".format(
			alias=connection_alias
		)
		try:
			with open(fn_access_token_cache, 'r') as f:
				access_token = json.loads(f.read())
				if not force_new_token and self._check_token_validity(access_token):
					self.logger.debug("Using cached access token, because it is still valid.")
					return access_token
		except Exception as e:
			self.logger.info(
				'The access token cache is empty or inaccessible.'
				' A new access token will be acquired. Error: {error}'.format(
					error=str(e)
				)
			)

		token_file_as_json = load_ids_file(connection_alias)

		endpoint = "https://login.microsoftonline.com/{directory_id}/oauth2/v2.0/token".format(
			directory_id=token_file_as_json['directory_id']
		)

		response = self._call_graph_api(
			'POST',
			endpoint,
			headers={'Content-Type': 'application/x-www-form-urlencoded'},
			data={  # NOTE do not use json.dumps here, because this is a different content-type!
				'client_id': token_file_as_json['application_id'],
				'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
				'client_assertion': get_client_assertion_from_alias(
					endpoint,
					connection_alias,
					token_file_as_json['application_id']
				),
				'grant_type': 'client_credentials',
				'scope': ['https://graph.microsoft.com/.default']
			},
			expected_status=[200],
			retry=0
		)

		# it would be nicer to use the Date field from the response.header
		# instead of datetime.now(), but the level of abstraction does not
		# easily allow to come by. We cheat a little and our result could be
		# inaccorate, but the error handling in _call_graph_api would retry
		# with a new token, if that ever happened.
		expires_on = datetime.datetime.now() + datetime.timedelta(
			seconds=response['expires_in']
		)

		# Note, that the Azure API has had a field with the same name
		# 'expires_on' in its result, whereas we calculate the value for it
		# here locally...
		response['expires_on'] = expires_on.strftime('%Y-%m-%dT%H:%M:%S')
		with open(fn_access_token_cache_tmp, 'w') as f:
			f.write(json.dumps(response))

		os.chmod(fn_access_token_cache_tmp, 0o600)
		os.chown(fn_access_token_cache_tmp, uid, gid)
		shutil.move(fn_access_token_cache_tmp, fn_access_token_cache)

		return response

	def _check_token_validity(self, token):
		expires_on = datetime.datetime.strptime(token['expires_on'], "%Y-%m-%dT%H:%M:%S")
		# newer python versions will simplify this with:
		# expires_on = datetime.fromisoformat(token['expires_on'])

		# write some information about the token in use into the log file
		self.logger.info(
			'The access token for `{alias}` looks'
			' similar to: `{starts}-trimmed-{ends}`.'
			' It is valid until {expires_on}'.format(
				starts=token['access_token'][:10],
				ends=token['access_token'][-10:],
				alias=self.connection_alias,
				expires_on=expires_on
			)
		)

		return (datetime.datetime.now() < expires_on)

	# ==========================================================================
	# the single most important function

	def _call_graph_api(self, method, url, data=None, retry=3, headers={}, expected_status=[], page=True):
		''' SUMMARY
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

			a Dict with the return values from the Micrsoft server
		'''

		values = {}  # holds data from pagination
		while url and url != "":  # as long as retries are left and url is set to a next page link
			msg = self._fprints_hide_pw(data, "GraphAPI: {method} {url}".format(method=method, url=url))
			self.logger.debug(msg)

			# prepare the http headers, which we are going to send with any request
			# the access_token should have been initialized in the constructor.
			# if not we still continue, because that allows us to use this function
			# for the acquisition of the access token as well.
			headers.update({'User-Agent': 'Univention Microsoft 365 Connector'})
			if hasattr(self, 'access_token_json'):
				headers.update({'Authorization': 'Bearer {}'.format(self.access_token_json['access_token'])})

			try:
				response = requests.request(
					method=method,
					url=url,
					verify=True,
					headers=headers,
					data=data,
					proxies=self.proxies,
					timeout=10
				)
			except requests.exceptions.Timeout:
				response = requests.request(
					method=method,
					url=url,
					verify=True,
					headers=headers,
					data=data,
					proxies=self.proxies,
					timeout=10
				)

			self.logger.info(
				"status: %r (%s) (%s %s)",
				response.status_code,
				"OK" if 200 <= response.status_code <= 299 else "FAIL",
				method.upper(),
				url)

			# check for a server error: which may be only temporary
			if 500 <= response.status_code <= 599:
				if retry:
					raise self._generate_error_message(response)
				else:
					self.logger.warning(
						"Microsoft Graph returned a server error, which"
						" could be temporarily. We will retry the same call"
						" in ten seconds again."
					)
					time.sleep(10)
					retry = retry - 1
					if retry > 0:
						continue  # restart the loop with the same url again
					else:
						raise self._generate_error_message(response, "Still a server error 500.")

			elif 401 == response.status_code:
				retry = retry - 1
				self.logger.debug("retries left: {retry}".format(retry=retry))
				if retry > 0:
					# retry a login ,then try the call again
					self.access_token_json = self._login(self.connection_alias)
					continue  # and retry with the new credentials
				else:
					raise self._generate_error_message(response, "Unable to (re-)login")

			elif 403 == response.status_code:
				retry = retry - 1
				if retry > 0:
					# retry with a new token
					retry = 1
					self.logger.info(
						"Getting a new token in case permissions have been updated")
					self.access_token_json = self._login(self.connection_alias, force_new_token=True)
					continue  # and retry with the new credentials
				else:
					self.logger.warn(
						"Authorization Error. Your application may not have the correct "
						"permissions for the Microsoft Graph API."
						"Please check https://help.univention.com/t/18453.")
					raise self._generate_error_message(response,
						"Authorization Error. Your application may not have the correct "
						"permissions for the Microsoft Graph API."
						"Please check https://help.univention.com/t/18453.")

			elif response.status_code not in expected_status:
				raise self._generate_error_message(response)

			elif not response.content:
				# an empty response is usually not an error and if the relevant
				# data are not in the body, they can usually be found in the
				# reponse headers...
				return dict(response.headers)

			else:
				try:
					response_json = response.json()

					if 'value' in values:
						values['value'].extend(response_json['value'])
					else:
						values = response_json

					if not (page and ('@odata.nextLink' in response_json)):
						# explicitly break the loop, because we are done
						break
					else:
						# implement pagination: as long as further pages follow, we
						# want to request these and as long as url is set, this loop
						# will append to the `values` array
						url = response_json.get("@odata.nextLink")
						self.logger.debug('Next page: {url}'.format(url=url))
						continue  # continue the loop with the next url

				except ValueError as exc:
					raise self._generate_error_message(
						response,
						"Response payload was not parseable by the json parser: {error}".format(
							error=str(exc)
						)
					)

		# the loop ends here. That means, that there were no further urls
		# returned for pagination. The result will now be an accumulated
		# `List` of all call results.
		return values

	# ==========================================================================
	# error handling starts here...

	def _generate_error_message(self, response, message=''):
		''' The Graph API (as well as the Azure API) is consistent in that way,
			that both return a small number of success values as http response
			status code and a larger number of possible error messages, which
			are much more consistent across different endpoints. This function
			is there to take advantage of that fact and it provides all the
			informations required to fix any problem: all request headers and
			the request body alongside with the responses counterparts.

			@return an Exception of type GraphError
		'''

		if isinstance(response, str):
			message += response

		elif isinstance(response, requests.Response):
			message += "HTTP response status: {num}\n".format(
				num=response.status_code
			)
			if hasattr(response, 'headers'):
				message += (
					"> request url: {req_url}\n\n"
					"> request header: {req_headers}\n\n"
					"> request body: {req_body}\n\n"
					"> response header: {headers}\n\n"
					"> response body: {body}\n\n"
				).format(
					req_url=str(response.request.url),
					req_headers=json.dumps(dict(response.request.headers), indent=2),
					req_body=self._try_to_prettify(response.request.body or "-NONE-"),
					headers=json.dumps(dict(response.headers), indent=2),
					body=self._try_to_prettify(response.content or "-NONE-")
				)
		elif response is None:
			message += "The response was of type `None`"
		else:
			message += 'unexpected error'

		return GraphError(message)

	def _try_to_prettify(self, json_string):
		try:
			return json.dumps(json.loads(json_string), indent=2)
		except ValueError:
			return json_string

	# ==========================================================================
	# plain API calls start here...

	def create_invitation(self, invitedUserEmailAddress, inviteRedirectUrl):
		''' https://docs.microsoft.com/en-us/graph/api/invitation-post
			returns: a user object of type `Guest`
		'''

		return self._call_graph_api(
			method='POST',
			url='https://graph.microsoft.com/v1.0/invitations',
			data=dict(
				{
					'invitedUserEmailAddress': quote(invitedUserEmailAddress, safe='@'),
					'inviteRedirectUrl': quote(inviteRedirectUrl, safe=':/')
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[201]
		)

	def list_azure_users(self):
		''' NOTE: This function should only be used for testing!
			This function calls the Azure API with a Graph access token.
			According to the documentation it should be doable somehow. As we
			do not need this function at the moment, it is kept here as a
			reminder and possible starting point if that becomes relevant in
			future, when we start implementing backwards compatiblity.
		'''
		return self._call_graph_api(
			method='GET',
			url='https://graph.windows.net/{application_id}/users?api-version=1.6'.format(
				application_id=self.auth.adconnection_id
			),
			expected_status=[200]
		)

	def list_graph_users(self):
		''' https://docs.microsoft.com/en-us/graph/api/user-list
		'''

		return self._call_graph_api(
			'GET', 'https://graph.microsoft.com/v1.0/users',
			expected_status=[200]
		)

	def get_me(self):
		''' https://docs.microsoft.com/en-us/graph/api/user-get
		'''

		return self._call_graph_api(
			'GET', 'https://graph.microsoft.com/v1.0/me',
			expected_status=[200]
		)

	def get_user(self, user_id):
		''' https://docs.microsoft.com/en-us/graph/api/user-get
		'''

		return self._call_graph_api(
			'GET', 'https://graph.microsoft.com/v1.0/users/{user_id}'.format(
				user_id=user_id
			),
			expected_status=[200]
		)

	def get_group(self, group_id, selection=None):
		''' https://docs.microsoft.com/en-us/graph/api/user-get
		'''

		if selection is None or selection == '':
			selection = ""
		else:
			selection = "?$select={selection}".format(selection=selection)

		return self._call_graph_api(
			'GET', 'https://graph.microsoft.com/v1.0/groups/{group_id}{select}'.format(
				group_id=group_id,
				select=selection
			),
			expected_status=[200]
		)

	def get_team(self, group_id):
		''' https://docs.microsoft.com/en-us/graph/api/team-get
		'''

		return self._call_graph_api(
			'GET', 'https://graph.microsoft.com/v1.0/teams/{group_id}'.format(
				group_id=group_id
			),
			expected_status=[200]
		)

	def create_team(self, name, owner, description=""):
		''' https://docs.microsoft.com/en-us/graph/api/team-post
		'''

		return self._call_graph_api(
			'POST', 'https://graph.microsoft.com/v1.0/teams',
			data=json.dumps(
				{
					'template@odata.bind':
						"https://graph.microsoft.com/v1.0/teamsTemplates('standard')",
					'displayName': name,
					'description': description,
					"members": [
						{
							"@odata.type": "#microsoft.graph.aadUserConversationMember",
							"roles": ["owner"],
							"user@odata.bind": "https://graph.microsoft.com/v1.0/users('{userid}')".format(
								userid=owner
							)
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
		''' https://docs.microsoft.com/en-us/graph/api/group-post-owners
		'''

		return self._call_graph_api(
			'POST', 'https://graph.microsoft.com/v1.0/groups/{group_id}/owners/$ref'.format(
				group_id=group_id
			),
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
		''' https://hutten.knut.univention.de/mediawiki/index.php/Security_Updates
		Once owners are assigned to a group, the last owner of the group cannot be removed.
		'''

		return self._call_graph_api(
			'DELETE', 'https://graph.microsoft.com/v1.0/groups/{group_id}/owners/{owner_id}/$ref'.format(
				group_id=group_id, owner_id=owner_id
			),
			expected_status=[
				204,  # 204 means success and has an empty content body according to MS
			]
		)

	def create_team_from_group(self, object_id):
		''' https://docs.microsoft.com/en-us/graph/api/team-put-teams

			Create a new team under a group.
			If the group was created less than 15 minutes ago, it's possible for the Create team call to fail
			with a 404 error code due to replication delays. The recommended pattern is to retry the Create team
			call three times, with a 10 second delay between calls.
		'''

		return self._call_graph_api(
			'POST',
			'https://graph.microsoft.com/v1.0/teams',
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
		''' https://docs.microsoft.com/en-us/graph/api/team-put-teams

			Here is the non-beta endpont version of the create_team_from_group
			function with limited functionality. It does e.g. not work with
			"Cannot migrate this group, id:
			364ff58b-b67a-4a74-8f6d-ac3e9ff7db38, access type: [...]
		'''

		return self._call_graph_api(
			'PUT',
			'https://graph.microsoft.com/v1.0/groups/{object_id}/team'.format(
				object_id=object_id
			),
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

	def delete_team(self, group_id):
		''' https://docs.microsoft.com/en-us/graph/api/group-delete

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
		'''

		return self._call_graph_api(
			'DELETE',
			'https://graph.microsoft.com/v1.0/groups/{group_id}'.format(
				group_id=group_id),
			expected_status=[204]
		)

	def archive_team(self, team_id):
		''' https://docs.microsoft.com/en-us/graph/api/team-archive

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
		'''

		return self._call_graph_api(
			'POST',
			'https://graph.microsoft.com/v1.0/teams/{team_id}/archive'.format(
				team_id=team_id
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[202]
		)

	def unarchive_team(self, team_id):
		''' https://docs.microsoft.com/en-us/graph/api/team-unarchive

			This function reactivates a team.

			RETURNS
			-------
			A http header with the `Location` of the restored team
		'''

		return self._call_graph_api(
			'POST',
			'https://graph.microsoft.com/v1.0/teams/{team_id}/unarchive'.format(
				team_id=team_id
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[202]
		)

	def list_team_members(self, team_id):
		''' https://docs.microsoft.com/en-us/graph/api/team-list-members
		'''

		return self._call_graph_api(
			'GET',
			'https://graph.microsoft.com/v1.0/teams/{team_id}/members'.format(
				team_id=team_id),
			expected_status=[200]
		)

	def add_team_member(self, team_id, user_id):
		''' https://docs.microsoft.com/en-us/graph/api/team-post-members

			PERMISSIONS
			-----------
			Application
				TeamMember.ReadWrite.All
		'''

		return self._call_graph_api(
			'POST',
			'https://graph.microsoft.com/v1.0/teams/{object_id}/members'.format(
				object_id=team_id
			),
			data=json.dumps(
				{
					"@odata.type": "#microsoft.graph.aadUserConversationMember",
					"user@odata.bind":
						"https://graph.microsoft.com/v1.0/users('{user_id}')".format(
							user_id=user_id)
				}
			),
			headers={'Content-Type': 'application/json'},
			expected_status=[201]
		)

	def add_group_member(self, group_id, object_id):
		'''
		https://docs.microsoft.com/en-us/graph/api/resources/teams-api-overview?view=graph-rest-1.0
		"To add members and owners to a team, change the membership of the group with the same ID."

		https://docs.microsoft.com/en-us/graph/api/group-post-members?view=graph-rest-1.0&tabs=http

		:param group_id: azure object id of group object
		:param object_id: azure object id of user object to add to the group
		:return: 2xx if okay, 400 if user already is member, 404 if object to be added does not exist
		'''
		return self._call_graph_api(
			'POST',
			'https://graph.microsoft.com/v1.0/groups/{group_id}/members/$ref'.format(
				group_id=group_id
			),
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

	def remove_group_member(self, group_id, object_id):
		'''
		https://docs.microsoft.com/en-us/graph/api/resources/teams-api-overview?view=graph-rest-1.0
		"To add/remove members and owners to a team, change the membership of the group with the same ID."

		https://docs.microsoft.com/en-us/graph/api/group-delete-members?view=graph-rest-1.0&tabs=http
		:param group_id: azure object id of group object
		:param object_id: azure object id of user object to remove from the group
		:return: 204 no content
		'''
		return self._call_graph_api(
			'DELETE',
			'https://graph.microsoft.com/v1.0/groups/{group_id}/members/{object_id}/$ref'.format(
				group_id=group_id,
				object_id=object_id
			),
			expected_status=[204]
		)

	def delete_team_member(self, team_id, membership_id):
		''' https://docs.microsoft.com/en-us/graph/api/team-post-members

			PERMISSIONS
			-----------
			Application
				User.ReadWrite.All
		'''

		return self._call_graph_api(
			'DELETE',
			'https://graph.microsoft.com/v1.0/teams/{team_id}/members/{membership_id}'.format(
				team_id=team_id,
				membership_id=membership_id),
			expected_status=[204]
		)

	def add_user(self, username, email, password):
		''' https://docs.microsoft.com/en-us/graph/api/user-post-users
		'''

		return self._call_graph_api(
			'POST',
			'https://graph.microsoft.com/v1.0/users',
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

	def test_list_team(self):
		''' https://docs.microsoft.com/en-us/graph/api/group-list

			Summary
			This function has the purpose to determine
			if the team functionality has the correct permissions
			set. This is called in the office365-group.py listener
			module.
		'''

		return self._call_graph_api(
			'GET',
			'https://graph.microsoft.com/v1.0/groups?'
			'$count',
			expected_status=[200], page=False
		)

	def list_teams(self):
		''' https://docs.microsoft.com/en-us/graph/api/group-list

			Summary
			-------

			this is a simplification which we should try to keep up to date
			with the API. This function could potentially return a very long
			array and its performance can be tuned with the `$top` parameter
			in the future, which allows pagination with more items per page
			and a maximum of 999 at the time of writing this comment. More
			info here: https://docs.microsoft.com/en-us/graph/paging
		'''

		return self._call_graph_api(
			'GET',
			'https://graph.microsoft.com/v1.0/groups?'
			'$select=id,displayName,resourceProvisioningOptions',
			expected_status=[200]
		)

	def convert_from_group_to_team(self, group_objectid, owner_objectids):
		# set owner
		for owner in owner_objectids:
			self.logger.debug("convert_from_group_to_team: add owner %r", owner)
			write_async_job(a_function_name='add_group_owner_to_team', a_ad_connection_alias=self.connection_alias, a_logger=self.logger, group_objectid=group_objectid, owner_objectid=owner)

		# convert to team
		write_async_job(a_function_name='create_or_unarchive_team', a_ad_connection_alias=self.connection_alias, a_logger=self.logger, group_objectid=group_objectid)
		return


class GraphAPIAsyncCalls(Graph):
	def __init__(self, ucr, name, connection_alias, logger=logger):
		super(GraphAPIAsyncCalls, self).__init__(ucr, name, connection_alias, logger)
		self.seconds_to_finish_azure_api_call = 180  # How long should an async method run and retry to make an API call
		self.seconds_between_api_calls = 10  # Wait interval between API calls

	def create_or_unarchive_team(self, group_objectid):
		# first check if team has to be unarchived
		team = None
		try:
			team = self.get_team(group_objectid)
		except GraphError as e:
			self.logger.info('no team found for {} ({})'.format(group_objectid, e))
		if team and team.get('isArchived', False):
			self.logger.info('unarchive team {}'.format(group_objectid))
			self.unarchive_team(group_objectid)
			return
		# create team
		self.logger.debug("Convert group %r to team", group_objectid)
		seconds_spend_in_method = 0
		while True:
			try:
				self.create_team_from_group(group_objectid)
				self.logger.debug("Successfully created team from group %r", group_objectid)
				return
			except GraphError as e:
				seconds_spend_in_method += 10
				if seconds_spend_in_method > self.seconds_to_finish_azure_api_call:
					self.logger.error("Giving up on converting group to team after too many API calls, %r", e)
					raise
				self.logger.debug("Error on create team, retry in %r seconds; %r", self.seconds_between_api_calls, e)
				time.sleep(self.seconds_between_api_calls)

	def add_group_owner_to_team(self, group_objectid, owner_objectid):
		''' https://docs.microsoft.com/en-us/graph/api/group-post-owners
		'''

		self.logger.debug("Add owner %r to group %r", owner_objectid, group_objectid)
		seconds_spend_in_method = 0
		while True:
			self.logger.debug("Add owner %r to group %r", owner_objectid, group_objectid)
			try:
				self.add_group_owner(group_objectid, owner_objectid)
				self.logger.debug("Successfully added owner %r to group %r", owner_objectid, group_objectid)
				return
			except GraphError as e:
				seconds_spend_in_method += 10
				if seconds_spend_in_method > self.seconds_to_finish_azure_api_call:
					self.logger.error("Giving up on adding owner to group %r", e)
					raise
				self.logger.debug("Error on adding owner, retry in %r seconds; %r", self.seconds_between_api_calls, e)
				time.sleep(self.seconds_between_api_calls)

# vim: filetype=python expandtab tabstop=4 shiftwidth=4 softtabstop=4
