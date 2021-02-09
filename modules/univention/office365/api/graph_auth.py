import os
import json
from univention.office365.api.exceptions import TokenFileNotFound, TokenFileInvalid


def load_token_file(alias, config_basepath="/etc/univention-office365"):
    '''
    finds the correct `token.json` file and checks the `consent_given` field
    within. The returned object is of type dict and has the enabled_connection
    as its name associated with with the json object, in which the access_token
    can
    be found.
        for c in consent_given_connections:
            print(c['access_token']
    may be easier to understand.
    '''

    token_file = os.path.join(config_basepath, alias, "token.json")
    if (os.path.exists(token_file)):
        with open(token_file, 'r') as f:
            token_json = json.load(f)
            if all([
                "access_token" in token_json,
                "access_token_exp_at" in token_json,
                "consent_given" in token_json,
                token_json["consent_given"]
            ]):
                return token_json
            else:
                raise TokenFileInvalid(
                    "An enabled connection has an unusuable access token:"
                    "{!r}".format(token_json))
    else:
        raise TokenFileNotFound()


def get_all_aliases_from_ucr(ucr):
    '''
    find all initialized connections according to the univention config registry...
    '''

    return [x[0].split('/')[-1] for x in filter(
        lambda x: all([
            x[0].startswith("office365/adconnection/alias/"),
            x[1] == 'initialized'
        ]), self.ucr.items())
    ]


def get_all_available_endpoints(ucr, config_basepath=None):
    '''
    returns a dict with the name of each `alias` and the endpoint in form of
    a plain json file. Basic checks are performed.
    '''

    endpoints = {}
    for a in get_all_aliases_from_ucr(ucr):
        endpoints[a] = load_token_file(ucr)
    return endpoints
