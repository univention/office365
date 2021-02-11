import datetime
import logging
import json
import requests
import sys

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote


from univention.office365.api.exceptions import GraphError
from univention.office365.api.graph_auth import load_token_file
from univention.office365.azure_handler import AzureHandler
from univention.office365.azure_auth import AzureAuth


class Graph(AzureHandler):
    def __init__(self, ucr, name, connection_alias, loglevel=logging.INFO):
        # initialize logging..
        self.initialized = False
        self.logger = logging.getLogger()
        self.logger.level = loglevel
        self.logger.addHandler(logging.StreamHandler(sys.stdout))

        if (self.logger.level == logging.DEBUG):
            logging.basicConfig(level=logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True

        # load the univention config registry for testing...
        self.ucr = ucr
        self.name = name
        self.connection_alias = connection_alias

        # # load the token file from disk and parses it into a json object
        # token_file_as_json = load_token_file(self.connection_alias)
        # self.logger.debug(json.dumps(token_file_as_json, indent=4))

        # # assign the value from the `access_token` field to the class variable
        # self.token = token_file_as_json['access_token']

        # # if the access token has expired (is too old), it is automatically
        # # tried to renew it. We use the old API calls for that, so that this
        # # is guaranteed to stay compatible for now.
        # valid_until = datetime.datetime.fromtimestamp(
        #     int(token_file_as_json.get("access_token_exp_at", 0))
        # )

        # # write some information about the token in use into the log file
        # self.logger.info(
        #     "The token for `{alias}` is valid until `{timestamp}` and it looks"
        #     " similar to: `{starts}-trimmed-{ends}`".format(
        #         starts=self.token[:10],
        #         ends=self.token[-10:],
        #         alias=self.connection_alias,
        #         timestamp=valid_until
        #     )
        # )

        # if (datetime.datetime.now() > valid_until):
        #     self.logger.info("Access token has expired. We will try to renew it.")
        #     self.token = AzureAuth(
        #         self.name,  # unique name in codebase making it easy to spot
        #         self.connection_alias
        #     ).retrieve_access_token()

        # TODO: remove these commented out lines - they are currently
        # be used for testing against the old login mechanism
        self.auth = AzureAuth(name, self.connection_alias)
        # initialized = self.auth.is_initialized(self.connection_alias)
        self.token = self.auth.get_access_token()

        # prepare the http headers, which we are going to send with any request
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {token}'.format(token=self.token),
            'User-Agent': 'ucs-microsoft365/1.0'  # not strictly needed
        }

    def create_random_pw(self):
        return super(Graph, self).create_random_pw()

    def _generate_error_message(self, response):
        if isinstance(response, str):
            message = response
        elif isinstance(response, requests.Response):
            if hasattr(response, 'headers'):
                message = "HTTP response header: {header}".format(
                    header=str(response.headers))
            else:
                message = "HTTP response status: {num}".format(
                    num=response.status_code)

            if hasattr(response, 'content'):
                message += response.content

        elif response is None:
            message = "The response was of type `None`"
        else:
            message('unexpected error')

        self.logger.debug('HTTP request headers: {header}'.format(
            header=json.dumps(self.headers, indent=4)))
        self.logger.debug('Token file: {json}'.format(
            json=json.dumps(load_token_file(self.connection_alias), indent=4)))

        return GraphError(message)

    def list_users(self, objectid=None, ofilter=None):
        return super(Graph, self).list_users(self, objectid, ofilter)

    def get_users_direct_groups(self, user_id):
        return super(Graph, self).get_users_direct_groups(self, user_id)

    def list_groups(self, objectid=None, ofilter=None):
        '''https://docs.microsoft.com/en-US/graph/api/group-list
        lists by default all groups. Filters are not implemented at the moment,
        because microsoft will provide such in future versions of the graph
        API, which is already accessible as `beta`. We have the choice to use
        the beta endpoint or implement the filtering in python for now.
        '''
        response = requests.get(
            'https://graph.microsoft.com/v1.0/groups',
            headers=self.headers
        )
        if (200 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def invalidate_all_tokens_for_user(self, user_id):
        return super(Graph, self).invalidate_all_tokens_for_user(self, user_id)

    def reset_user_password(self, user_id):
        return super(Graph, self).reset_user_password(self, user_id)

    def create_user(self, attributes):
        return super(Graph, self).create_user(self, attributes)

    def create_invitation(self, invitedUserEmailAddress, inviteRedirectUrl):
        ''' returns: a user object of type `Guest` '''
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
        ''' https://docs.microsoft.com/de-de/graph/api/group-post-groups '''
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

    def get_azure_domains(self):
        from univention.office365.azure_auth import resource_url
        self.auth = AzureAuth("TEST", self.connection_alias)
        # self.uris = self._get_azure_uris(self.auth.adconnection_id)
        graph_base_url = "{0}/{1}".format(resource_url, self.auth.adconnection_id)
        response = requests.get(
            "{base_url}/domains?api-version=1.6".format(base_url=graph_base_url),
            headers=self.headers)
        if (200 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def get_me(self):
        ''' https://docs.microsoft.com/en-US/graph/api/user-get '''
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers=self.headers
        )
        if (200 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def modify_user(self, object_id, modifications):
        return super(Graph, self).modify_user(self, object_id, modifications)

    def modify_group(self, object_id, modifications):
        return super(Graph, self).modify_group(self, object_id, modifications)

    def delete_user(self, object_id):
        return super(Graph, self).delete_user(self, object_id)

    def delete_group(self, object_id):
        return super(Graph, self).delete_group(self, object_id)

    def member_of_groups(self, object_id, resource_collection="users"):
        return super(Graph, self).member_of_groups(self, object_id, resource_collection)

    def member_of_objects(self, object_id, resource_collection="users"):
        return super(Graph, self).member_of_objects(self, object_id, resource_collection)

    def resolve_object_ids(self, object_ids, object_types=None):
        return super(Graph, self).resolve_object_ids(self, object_ids, object_types)

    def get_groups_direct_members(self, group_id):
        return super(Graph, self).get_groups_direct_members(self, group_id)

    def add_objects_to_azure_group(self, group_id, object_ids):
        return super(Graph, self).add_objects_to_azure_group(self, group_id, object_ids)

    def delete_group_member(self, group_id, member_id):
        return super(Graph, self).delete_group_member(self, group_id, member_id)

    def add_license(self, user_id, sku_id, deactivate_plans=None):
        return super(Graph, self).add_license(self, user_id, sku_id, deactivate_plans)

    def remove_license(self, user_id, sku_id):
        return super(Graph, self).remove_license(self, user_id, sku_id)

    def list_subscriptions(self, object_id=None, ofilter=None):
        return super(Graph, self).list_subscriptions(self, object_id, ofilter)

    def get_enabled_subscriptions(self):
        return super(Graph, self).get_enabled_subscriptions(self)

    def list_domains(self, domain_name=None):
        return super(Graph, self).list_domains(self, domain_name)

    def list_adconnection_details(self):
        return super(Graph, self).list_adconnection_details(self)

    def list_verified_domains(self):
        return super(Graph, self).list_verified_domains(self)

    def get_verified_domain_from_disk(self):
        return super(Graph, self).get_verified_domain_from_disk(self)

    def deactivate_user(self, object_id, rename=False):
        return super(Graph, self).deactivate_user(self, object_id, rename)

    def deactivate_group(self, object_id):
        return super(Graph, self).deactivate_group(self, object_id)

    def directory_object_urls_to_object_ids(self, urls):
        return super(Graph, self).directory_object_urls_to_object_ids(self, urls)

    # Microsoft Teams
    def create_team(self, name, description=""):
        ''' https://docs.microsoft.com/de-de/graph/api/team-post '''
        response = requests.put(
            "https://graph.microsoft.com/v1.0/groups/9c14ee2f-f926-4a3b-80e2-7ed63deb22c8/teams",
            headers=self.headers,
            data=json.dumps(
                {
                    'template@odata.bind':
                        "https://graph.microsoft.com/v1.0/teamsTemplates('standard')",

                    'displayName': quote(name),
                    'description': quote(description),
                }
            )
        )

        if (202 == response.status_code):
            return response.content
        else:
            raise self._generate_error_message(response)

    def create_team_from_group(self, object_id):  # object_id is similar to cb57b853-be97-457c-8232-491dd82f5940
        '''
        https://docs.microsoft.com/de-de/graph/api/team-put-teams?view=graph-rest-beta
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

    def list_all_teams(self):
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
