import logging
import json
import requests
import univention.office365.api.exceptions

from urllib.parse import urlencode
from univention.office365.api.base import Base as APIBase
from univention.office365.api.graph_auth import load_token_file
from univention.office365.azure_handler import Azure as AzureBase


class Graph(APIBase, AzureBase):
    def __init__(self, ucr, name, connection_alias):
        # initialize logging..
        self.initialized = False
        self.logger = logging.getLogger()
        self.logger.level = logging.INFO
        self.logger.addHandler(logging.StreamHandler(sys.stdout))

        # load the univention config registry for testing...
        self.ucr = ucr
        self.name = name
        self.connection_alias = connection_alias

        # if connection_alias is left out: load all available aliases.
        token_file_as_json = load_token_file(self.connection_alias)

        access_token_exp_at = datetime.datetime.fromtimestamp(
            int(token_file_as_json.get("access_token_exp_at", 0)))

        if datetime.datetime.now() > access_token_exp_at:
            logger.debug("Access token has expired. We will try to renew it.")
            self._access_token = self.retrieve_access_token()

        if not self._access_token_exp_at or datetime.datetime.now() > self._access_token_exp_at:

        self.token = self.token_file_as_json['access_token']
        self.headers = {
            "Authorization": ("Bearer %s" % self.token),
            "Content-Type": "application/json"
        }

    def create_random_pw(self):
        return super(Graph, self).create_random_pw()

    def _generate_error_message(self, response):
        # TODO: some logging and interprestation and based on that
        # return a different type of exception
        message = "[%s]: %s" % (str(response.header), response.content)
        self.logger.error(message)
        return GraphError(message)

    def retrieve_access_token(self):
        # TODO reimplmentation of that
        assertion = self._get_client_assertion()

        post_form = {
                'resource': resource_url,
                'client_id': self.client_id,
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': assertion,
                'grant_type': 'client_credentials',
                'redirect_uri': self.reply_url,
                'scope': SCOPE
        }
        url = oauth2_token_url.format(adconnection_id=self.adconnection_id)

        logger.debug("POST to URL=%r with data=%r", url, post_form)
        response = requests.post(url, data=post_form, verify=True, proxies=self.proxies)
        if response.status_code != 200:
                logger.exception("Error retrieving token (status %r), response: %r", response.status_code, response.__dict__)
                raise TokenError(_("Error retrieving authentication token from Azure for AD connection {adconnection}.").format(adconnection=self.adconnection_alias), response=response, adconnection_alias=self.adconnection_alias)
        at = response.json
        if callable(at):  # requests version compatibility
                at = at()
        logger.debug("response: %r", at)
        if "access_token" in at and at["access_token"]:
                self._access_token = at["access_token"]
                self._access_token_exp_at = datetime.datetime.fromtimestamp(int(at["expires_on"]))
                self.store_tokens(adconnection_alias=self.adconnection_alias, access_token=at["access_token"], access_token_exp_at=at["expires_on"])
                return at["access_token"]
        else:
                logger.exception("Response didn't contain an access_token. response: %r", response)
                raise TokenError(_("Error retrieving authentication token from Azure for AD connection {adconnection}.").format(adconnection=self.adconnection_alias), response=response, adconnection_alias=self.adconnection_alias)


    def list_users(self, objectid=None, ofilter=None):
        return super(Graph, self).list_users(self, objectid, ofilter)

    def get_users_direct_groups(self, user_id):
        return super(Graph, self).get_users_direct_groups(self, user_id)

    def list_groups(self, objectid=None, ofilter=None):
        return super(Graph, self).list_groups(self, objectid, ofilter)

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
                    'invitedUserEmailAddress': urlencode(invitedUserEmailAddress),
                    'inviteRedirectUrl': urlencode(inviteRedirectUrl)
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
                    'displayName': urlencode(name),
                    'description': urlencode(description),
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

                    'displayName': urlencode(name),
                    'description': urlencode(description),
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
                team_id=object_id),
            headers=self.headers)

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
