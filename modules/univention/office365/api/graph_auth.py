# required dependencies for rsa signing and certificate handling
# all done in get_client_assertion.
import base64
import rsa
import time
import uuid

# basics
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
        for c in get_all_aliases_from_ucr(ucr):
            print(c['access_token']
    may be easier to understand.
    '''

    with open(os.path.join(config_basepath, alias, "ids.json"), 'r') as f_ids, \
         open(os.path.join(config_basepath, alias, "token.json"), 'r') as f_token:

        ids_json = json.load(f_ids)
        token_json = json.load(f_token)
        if all([
            "access_token" in token_json,
            "access_token_exp_at" in token_json,
            "client_id" in ids_json
        ]):
            token_json['application_id'] = ids_json['client_id']  # name has changed with graph!
            token_json['directory_id'] = ids_json['adconnection_id']  # also known as 'tenant id'
            return token_json
        else:
            raise TokenFileInvalid(
                "An enabled connection has an unusuable access token:"
                "{!r}".format(token_json))


def get_all_aliases_from_ucr(ucr):
    ''' finds all initialized connections according to the univention config registry '''

    return [x[0].split('/')[-1] for x in filter(
        lambda x: all([
            x[0].startswith("office365/adconnection/alias/"),
            x[1] == 'initialized'
        ]), ucr.items())
    ]


def _get_client_assertion(oauth_token_endpoint, ssl_fingerprint, key_data, application_id):
    client_assertion_header = {
        'alg': 'RS256',
        'x5t': ssl_fingerprint,
    }

    # thanks to Vittorio Bertocci for this:
    # http://www.cloudidentity.com/blog/2015/02/06/requesting-an-aad-token-with-a-certificate-without-adal/
    not_before = int(time.time()) - 300  # -5min to allow time diff between us and the server
    exp_time = int(time.time()) + 600  # 10min
    client_assertion_payload = {
        'sub': application_id,
        'iss': application_id,
        'jti': str(uuid.uuid4()),
        'exp': exp_time,
        'nbf': not_before,
        'aud': oauth_token_endpoint
    }

    header_string = json.dumps(client_assertion_header).encode('utf-8')
    encoded_header = base64.urlsafe_b64encode(header_string).decode('utf-8').strip('=')
    payload_string = json.dumps(client_assertion_payload).encode('utf-8')
    encoded_payload = base64.urlsafe_b64encode(payload_string).decode('utf-8').strip('=')
    assertion_blob = '{0}.{1}'.format(encoded_header, encoded_payload)  # <base64-encoded-header>.<base64-encoded-payload>

    priv_key = rsa.PrivateKey.load_pkcs1(key_data)
    _signature = rsa.sign(assertion_blob.encode('utf-8'), priv_key, 'SHA-256')
    encoded_signature = base64.urlsafe_b64encode(_signature)
    encoded_signature_string = encoded_signature.decode('utf-8').strip('=')
    signature = encoded_signature_string

    # <base64-encoded-header>.<base64-encoded-payload>.<base64-encoded-signature>
    return '{assertion}.{signature}'.format(
        assertion=assertion_blob,
        signature=signature
    )


def get_client_assertion(oauth_endpoint, connection_alias, application_id, config_basepath="/etc/univention-office365"):
    with open(os.path.join(config_basepath, connection_alias, "cert.fp"), 'r') as f_ssl_fingerprint,\
         open(os.path.join(config_basepath, connection_alias, "key.pem"), 'r') as f_ssl_key:

        return _get_client_assertion(
            oauth_endpoint,
            f_ssl_fingerprint.read(),
            f_ssl_key.read(),
            application_id
        )
