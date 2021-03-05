import os
import rsa
import time
import json
import uuid
import base64


def get_client_assertion(oauth_token_endpoint, ssl_fingerprint, key_data, application_id):
    def _get_assertion_blob(header, payload):
        header_string = json.dumps(header).encode('utf-8')
        encoded_header = base64.urlsafe_b64encode(header_string).decode('utf-8').strip('=')
        payload_string = json.dumps(payload).encode('utf-8')
        encoded_payload = base64.urlsafe_b64encode(payload_string).decode('utf-8').strip('=')
        return '{0}.{1}'.format(encoded_header, encoded_payload)  # <base64-encoded-header>.<base64-encoded-payload>

    def _get_signature(message, key_data):
        priv_key = rsa.PrivateKey.load_pkcs1(key_data)
        _signature = rsa.sign(message.encode('utf-8'), priv_key, 'SHA-256')
        encoded_signature = base64.urlsafe_b64encode(_signature)
        encoded_signature_string = encoded_signature.decode('utf-8').strip('=')
        return encoded_signature_string

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

    assertion_blob = _get_assertion_blob(client_assertion_header, client_assertion_payload)
    signature = _get_signature(assertion_blob, key_data)

    # <base64-encoded-header>.<base64-encoded-payload>.<base64-encoded-signature>
    client_assertion = '{0}.{1}'.format(assertion_blob, signature)

    return client_assertion


def get_client_assertion_from_alias(
    oauth_endpoint,
    connection_alias,
    application_id,
    config_basepath="/etc/univention-office365"
):
    with open(os.path.join(config_basepath, connection_alias, "cert.fp"), 'r') as f_ssl_fingerprint,\
         open(os.path.join(config_basepath, connection_alias, "key.pem"), 'r') as f_ssl_key:

        return get_client_assertion(
            oauth_endpoint,
            f_ssl_fingerprint.read(),
            f_ssl_key.read(),
            application_id
        )
