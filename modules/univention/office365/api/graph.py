import datetime
import logging
import json
import requests
import sys

try:
    from urllib.parse import quote, urlencode
except ImportError:
    from urllib import quote, urlencode


from univention.office365.api.exceptions import GraphError
from univention.office365.api.graph_auth import get_client_assertion, load_token_file
from univention.office365.azure_handler import AzureHandler
from univention.office365.azure_auth import AzureAuth


class Graph(AzureHandler):
    def __init__(self, ucr, name, connection_alias, logger=logging.getLogger()):
        '''
        This initialisation function is parameter compatible with the former
        `azure_handler.py` class and can be used as a drop-in-replacement for
        it. It still relies on the AzureHandlers functionality and acts as a
        compatibility layer, while it simultaneously allows the incremental
        reimplementation of functions on top of it, or in other words
        'overwrite functions' until all calls have been migrated, then remove
        the base class `AzureHandler`.
        '''

        self.ucr = ucr
        self.name = name
        self.connection_alias = connection_alias
        self.logger = logger

        if (self.logger.level == logging.DEBUG):
            logging.basicConfig(level=logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True
            requests_log.addHandler(logging.StreamHandler(sys.stdout))
            # requests.settings.verbose = sys.stderr

        # self.access_token = self._login(connection_alias)
        self.access_token_json = json.loads(self._login(connection_alias))
        self.token = self.access_token_json['access_token']

        # write some information about the token in use into the log file
        self.logger.info(
            "The token for `{alias}` looks"
            " similar to: `{starts}-trimmed-{ends}`".format(
                starts=self.access_token_json['access_token'][:10],
                ends=self.access_token_json['access_token'][-10:],
                alias=self.connection_alias,
            )
        )

        # prepare the http headers, which we are going to send with any request
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.access_token_json['access_token']),
            'User-Agent': 'Univention Microsoft 365 Connector'
        }

        # initialize backward compatibility with Azure...
        super(Graph, self).__init__(ucr, name, connection_alias)
        if (not hasattr(self, 'auth')):  # TODO check if still necessary
            logger.warn(
                "Implementation changed!"
                "The base class initialisation did not set self.auth."
                "Trying to fix that problem by adding necessary values."
            )
            self.auth = AzureAuth(name, self.connection_alias)
            self.token = self.auth.get_access_token()

    def create_random_pw(self):
        return super(Graph, self).create_random_pw()

    def _try_to_prettify(self, json_string):
        try:
            return json.dumps(json.loads(json_string), indent=2)
        except ValueError:
            return json_string

    def _login(self, connection_alias):
        # https://login.microsoftonline.com/3e7d9eb5-c3a1-4cfc-892e-a8ec29e45b77/oauth2/v2.0/token
        token_file_as_json = load_token_file(connection_alias)

        # TODO: compatibility between azure and graph vvv

        # endpoint = "https://login.microsoftonline.com/{directory_id}/oauth2/token".format(
        #     directory_id=token_file_as_json['directory_id']
        # )

        # with the new graph endpoint the directory_id becomes optional
        # https://docs.microsoft.com/en-us/graph/migrate-azure-ad-graph-request-differences#basic-requests
        endpoint = "https://login.microsoftonline.com/{directory_id}/oauth2/v2.0/token".format(
            directory_id=token_file_as_json['directory_id']
        )

        response = requests.post(
            endpoint,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'client_id': token_file_as_json['application_id'],
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': get_client_assertion(
                    endpoint,
                    connection_alias,
                    token_file_as_json['application_id']
                ),
                'grant_type': 'client_credentials',
                'scope': ['https://graph.microsoft.com/.default']
            }
        )

        if (200 == response.status_code):  # a new user was created
            return response.content
        else:
            raise self._generate_error_message(response)

    def _generate_error_message(self, response):
        if isinstance(response, str):
            message = response

        elif isinstance(response, requests.Response):
            message = "HTTP response status: {num}\n".format(
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
            message = "The response was of type `None`"
        else:
            message('unexpected error')

        # self.logger.debug(message)
        return GraphError(message)

    def create_invitation(self, invitedUserEmailAddress, inviteRedirectUrl):
        ''' https://docs.microsoft.com/en-us/graph/api/invitation-post
            returns: a user object of type `Guest`
        '''

        response = requests.post(
            "https://graph.microsoft.com/v1.0/invitations",
            headers=self.headers,
            data=json.dumps(
                {
                    'invitedUserEmailAddress': quote(invitedUserEmailAddress, safe='@'),
                    'inviteRedirectUrl': quote(inviteRedirectUrl, safe=':/')
                }
            )
        )

        if (201 == response.status_code):  # a new user was created
            return response.content
        else:
            raise self._generate_error_message(response)

    def create_group(self, name, description=""):
        ''' https://docs.microsoft.com/en-us/graph/api/group-post-groups '''
        response = requests.post(
            "https://graph.microsoft.com/v1.0/groups",
            headers=self.headers,
            data=json.dumps(
                {
                    'displayName': quote(name),
                    'description': quote(description),
                    'mailEnabled': False,
                    'mailNickname': name.translate(
                        ''.maketrans(
                            {' ': '_-_'}),  # translate ' ' to '_-_' and
                        '@()\\[]";:.<>,'),  # delete illegal chars (see doc)
                    'securityEnabled': True
                }
            )
        )

        if (201 == response.status_code):  # group was created
            return response.content
        else:
            raise self._generate_error_message(response)

    def list_azure_users(self):
        response = requests.get(
            "https://graph.windows.net/{application_id}/users?api-version=1.6".format(
                application_id=self.auth.adconnection_id
            ),
            headers=self.headers)
        if (200 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def list_graph_users(self):
        response = requests.get(
            "https://graph.microsoft.com/v1.0/users",
            headers=self.headers
        )
        if (200 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def get_me(self):
        ''' https://docs.microsoft.com/en-us/graph/api/user-get '''
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers=self.headers
        )
        if (200 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def list_groups(self, objectid="", filter=""):
        ''' https://docs.microsoft.com/en-us/graph/api/group-list '''
        ''' we keep objectid for backward compatibility for now '''
        response = requests.get(
            "https://graph.microsoft.com/v1.0/groups?filter={filter}".format(
                filter=filter
            ), headers=self.headers,
        )
        if (200 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    # Microsoft Teams
    def create_team(self, name, description="", owner=None):
        ''' https://docs.microsoft.com/en-us/graph/api/team-post '''
        response = requests.post(
            "https://graph.microsoft.com/v1.0/teams",
            headers=self.headers,
            data=json.dumps(
                {
                    'template@odata.bind':
                        "https://graph.microsoft.com/v1.0/teamsTemplates('standard')",
                    'displayName': name,
                    'description': description,
                    "members": [
                        {
                            "@odata.type":"#microsoft.graph.aadUserConversationMember",
                            "roles": ["owner"],
                            "user@odata.bind": "https://graph.microsoft.com/v1.0/users('{userid}')".format(
                                userid=owner
                            )
                        }
                    ]
                }
            )
        )

        if (202 == response.status_code):
            # the response body is empty in this case, interesting fields are
            # Location and Content-Location as they contain the new teams id
            return dict(response.headers)
        else:
            raise self._generate_error_message(response)

    def create_team_from_group(self, object_id):  # object_id is similar to cb57b853-be97-457c-8232-491dd82f5940
        '''
        https://docs.microsoft.com/en-us/graph/api/team-put-teams?view=graph-rest-beta
        @TODO: the name of this endpoint will change at one point in time. Regular tests are necessary.
        '''
        response = requests.post(
            "https://graph.microsoft.com/beta/teams",
            headers=self.headers,
            data=json.dumps(
                {
                    "template@odata.bind":
                        "https://graph.microsoft.com/beta/teamsTemplates('standard')",

                    "group@odata.bind":
                        "https://graph.microsoft.com/v1.0/groups('{object_id}')".format(
                            object_id=object_id)
                }
            )
        )

        if (201 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def delete_team(self, object_id):
        """ https://docs.microsoft.com/en-us/graph/api/group-delete """
        # links to the `delete group` page in the API doc on the MS website
        return self.delete_group(self, object_id)

    def list_team_members(self, team_id):
        ''' https://docs.microsoft.com/en-us/graph/api/team-list-members '''
        response = requests.get(
            "https://graph.microsoft.com/v1.0/teams/{team_id}/members".format(
                team_id=team_id),
            headers=self.headers
        )

        if (200 == response.status_code):
            return response.reason  # returns `Created` (200)
        else:
            raise self._generate_error_message(response)

    def add_team_member(self, team_id, user_id):
        ''' https://docs.microsoft.com/en-us/graph/api/team-post-members '''
        response = requests.post(
            "https://graph.microsoft.com/v1.0/teams/{object_id}/members".format(
                object_id=team_id
            ),
            headers=self.headers,
            data=json.dumps(
                {
                    "roles": ["owner"],
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "user@odata.bind":
                        "https://graph.microsoft.com/v1.0/users('{user_id}')".format(
                            user_id=user_id)
                }
            )
        )

        if (201 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def delete_team_member(self, team_id, membership_id):
        ''' https://docs.microsoft.com/en-us/graph/api/team-post-members '''
        response = requests.delete(
            "https://graph.microsoft.com/v1.0/teams/{team_id}/members/{membership_id}".format(
                team_id=team_id,
                membership_id=membership_id),
            headers=self.headers
        )

        if (204 == response.status_code):
            return response.reason  # returns `No Content` (204)
        else:
            raise self._generate_error_message(response)

    def get_team(self, group_id):
        ''' https://docs.microsoft.com/en-us/graph/api/team-get '''
        response = requests.get(
            "https://graph.microsoft.com/v1.0/teams/{group_id}".format(
                group_id=group_id)
        )

        if (200 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def list_teams(self):
        '''
        https://docs.microsoft.com/en-us/graph/teams-list-all-teams
        To list all teams in an organization (tenant), you find all groups that
        have teams, and then get information for each team.

        @TODO: the name of this endpoint will change at one point in time. Regular tests are necessary.
        '''
        # step 1: find all groups having teams within...
        response = requests.get(
            "https://graph.microsoft.com/beta/groups?$filter=resourceProvisioningOptions/Any(x:x eq 'Team')",
            headers=self.headers)

        # sanity check
        if (200 != response.status_code):
            raise self._generate_error_message(response)

        response_json = json.loads(response.content)

        # sanity check
        if response_json['@odata.context'] == "https://graph.microsoft.com/beta/$metadata#groups":
            raise self._generate_error_message(response)

        retval = json.dumps("")

        for group in response_json['value']:

            # sanity check
            if 'Team' not in group['resourceProvisioningOptions']:
                raise self._generate_error_message(response)

            team = json.loads(self.get_team(group['id']).content)
            # sanity check
            if 'isArchived' not in team:
                raise self._generate_error_message(response)

            # append team to the return value json...
            retval.update(team)

        return json.dumps(retval)
