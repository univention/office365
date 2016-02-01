#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle Azure oauth calls
#
# Copyright 2016 Univention GmbH
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


from urllib import urlencode
import requests
import json
import base64
import logging
import uuid
import time
import rsa
import socket
import os
import traceback
import datetime
import sys
from xml.dom.minidom import parseString
from functools import wraps
from stat import S_IRUSR, S_IWUSR

from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend
import OpenSSL.crypto
import jwt

import univention.debug as ud

NAME = "office365"
CONFDIR = "/etc/univention-office365"
SSL_KEY = CONFDIR + "/key.pem"
SSL_CERT = CONFDIR + "/cert.pem"
SSL_CERT_FP = CONFDIR + "/cert.fp"
IDS_FILE = CONFDIR + "/ids.json"
TOKEN_FILE = CONFDIR + "/token.json"
REDIRECT_URI = "https://{0}/univention-office365/reply".format(socket.getfqdn()).lower()
SCOPE = ["Directory.ReadWrite.All"]  # https://msdn.microsoft.com/Library/Azure/Ad/Graph/howto/azure-ad-graph-api-permission-scopes#DirectoryRWDetail
DEBUG_FORMAT = '%(asctime)s %(levelname)-8s %(module)s.%(funcName)s:%(lineno)d  %(message)s'
LOG_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


oauth2_auth_url = "https://login.microsoftonline.com/common/oauth2/authorize?{params}"
oauth2_token_url = "https://login.microsoftonline.com/{tenant_id}/oauth2/token"
oauth2_token_issuer = "https://sts.windows.net/{tenant_id}/"
federation_metadata_url = "https://login.microsoftonline.com/{tenant_id}/federationmetadata/2007-06/federationmetadata.xml"
resource_url = "https://graph.windows.net"

# global listener variable for decorator for static methods
glistener = None

# python logging works better for development, we can remove it later
logger = logging.getLogger("office365")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("/var/log/univention/office365-py.log")
fh.setFormatter(logging.Formatter(fmt=DEBUG_FORMAT, datefmt=LOG_DATETIME_FORMAT))
logger.addHandler(fh)


class TokenError(Exception):
	def __init__(self, response):
		if hasattr(response, "json"):
			j = response.json
			if callable(response.json):  # requests version compatibility
				j = j()
			msg = j["error_description"]
		else:
			msg = response.__dict__
		self.response = response
		log_e(msg)
		super(TokenError, self).__init__(msg)


class IDTokenError(Exception):
	pass


class TokenValidationError(Exception):
	pass


class NoIDsStored(Exception):
	pass


def _log(level, msg):
	if isinstance(msg, unicode):
		msg = msg.encode("utf-8")
	ud.debug(ud.LISTENER, level, "{}: {}".format(NAME, msg))


def log_a(msg):
	_log(ud.ALL, msg)
	logger.debug(msg)


def log_e(msg):
	_log(ud.ERROR, msg)
	logger.error(msg)


def log_ex(msg):
	_log(ud.ERROR, "%s, Exception: %s" % (msg, traceback.format_exc()))
	logger.exception(msg)


def log_p(msg):
	_log(ud.PROCESS, msg)
	logger.info(msg)


def run_as_root(func):
	@wraps(func)
	def _decorated(*args, **kwargs):
		if os.geteuid() == 0 or glistener is None:
			return func(*args, **kwargs)

		try:
			glistener.setuid(0)
			return func(*args, **kwargs)
		finally:
			glistener.unsetuid()
	return _decorated


def is_initialized():
	try:
		AzureAuth.load_azure_ids()
		return True
	except (NoIDsStored, IOError) as exc:
		log_e("is_initialized() {}".format(exc))
		return False


class AzureAuth(object):
	def __init__(self, listener, name):
		global NAME, glistener
		self.listener = listener
		NAME = name
		glistener = listener

		self.client_id, self.tenant_id = AzureAuth.load_azure_ids()
		self._access_token = None
		self._access_token_exp_at = None

	@staticmethod
	@run_as_root
	def load_azure_ids():
		with open(IDS_FILE, "r") as f:
			ids = json.load(f)
		if not isinstance(ids, dict) or "client_id" not in ids or "tenant_id" not in ids:
			raise NoIDsStored("Could not load client_id and tenant_id from {}.".format(IDS_FILE))
		return ids["client_id"], ids["tenant_id"]

	@staticmethod
	@run_as_root
	def store_azure_ids(client_id, tenant_id):
		open(IDS_FILE, "w").close()  # touch
		try:
			os.chmod(IDS_FILE, S_IRUSR | S_IWUSR)
		except OSError:
			pass
		with open(IDS_FILE, "w") as f:
			json.dump(dict(client_id=client_id, tenant_id=tenant_id), f)

	@staticmethod
	@run_as_root
	def load_tokens():
		try:
			with open(TOKEN_FILE, "r") as f:
				tokens = json.load(f)
		except IOError:
			tokens = dict()
		if not isinstance(tokens, dict):
			log_e("AzureAuth.load_tokens() Bad content of tokens file: '{}'.".format(tokens))
			tokens = dict()
		return tokens

	@staticmethod
	@run_as_root
	def store_tokens(**kwargs):
		tokens = AzureAuth.load_tokens()
		tokens.update(kwargs)
		open(TOKEN_FILE, "w").close()  # touch
		try:
			os.chmod(TOKEN_FILE, S_IRUSR | S_IWUSR)
		except OSError:
			pass
		with open(TOKEN_FILE, "w") as f:
			json.dump(tokens, f)

	def get_access_token(self):
		if not self._access_token:
			log_a("AzureAuth.get_access_token() loading token from disk...")
			tokens = AzureAuth.load_tokens()
			self._access_token = tokens.get("access_token")
			self._access_token_exp_at = datetime.datetime.fromtimestamp(int(tokens.get("access_token_exp_at")))
		if not self._access_token_exp_at or datetime.datetime.now() > self._access_token_exp_at:
			log_a("AzureAuth.get_access_token() token expired, retrieving now one from azure...")
			self._access_token = self.retrieve_access_token()
		log_a("AzureAuth.get_access_token() token valid until: {} : {}...{}".format(
			self._access_token_exp_at.isoformat(), self._access_token[:10], self._access_token[-10:]))
		return self._access_token

	@staticmethod
	def get_authorization_url(client_id):
		nonce = str(uuid.uuid4())
		AzureAuth.store_tokens(nonce=nonce)

		params = {
			'client_id': client_id,
			'redirect_uri': REDIRECT_URI,
			'response_type': 'code id_token',
			'scope': 'openid',
			'nonce': nonce,
			'prompt': 'admin_consent',
			'response_mode': 'form_post',
			'resource': resource_url,
		}
		return oauth2_auth_url.format(params=urlencode(params))

	@staticmethod
	def parse_id_token(id_token):
		def _decode_b64(base64data):
			# base64 strings should have a length divisible by 4
			# If this one doesn't, add the '=' padding to fix it
			leftovers = len(base64data) % 4
			if leftovers == 2:
				base64data += '=='
			elif leftovers == 3:
				base64data += '='

			decoded = base64.b64decode(base64data)
			return decoded.decode('utf-8')

		def _parse_token(encoded_token):
			# JWT tokens have 3 segments: header, body, signature.
			try:
				_header, _body, _signature = encoded_token.split(".")
				decoded_header = _decode_b64(_header)
				decoded_body = _decode_b64(_body)
				return json.loads(decoded_header), json.loads(decoded_body), _signature
			except:
				if sys.version_info < (3,):
					et = unicode(encoded_token, 'utf8')
				else:
					et = encoded_token
				log_ex(u"AzureAuth.parse_token(): Invalid token value: {0}".format(et))
				raise IDTokenError("Error parsing token: {}".format(traceback.format_exc()))

		def _get_azure_certs(tenant_id):
			# there's a strange non-ascii char at the beginning of the xml doc...
			def _discard_garbage(text):
				for pos, char in enumerate(text):
					if char == "<":
						return text[pos:]
			# the certificates with which the tokens were signed can be downloaded from the federation metadata document
			# https://msdn.microsoft.com/en-us/library/azure/dn195592.aspx
			try:
				fed = requests.get(federation_metadata_url.format(tenant_id=tenant_id))
			except:
				raise TokenValidationError("Could not download federation metadata: {}".format(traceback.format_exc()))
			# the federation metadata document is a XML file
			dom_tree = parseString(_discard_garbage(fed.text))
			# the certificates we want are inside:
			# <EntityDescriptor>
			#  <RoleDescriptor xsi:type="fed:SecurityTokenServiceType">  (<- the same certificates can be found in ApplicationServiceType/SAML too)
			#    <KeyDescriptor use="signing">                           (<- must be use="signing")
			#      <X509Certificate>
			certs = set()
			collection = dom_tree.documentElement
			# walk xml tree, checking conditions, collecting certificates and mccabes
			for rd_elem in collection.getElementsByTagName("RoleDescriptor"):
				if rd_elem.getAttribute("xsi:type") == "fed:SecurityTokenServiceType":
					for kd_elem in rd_elem.getElementsByTagName("KeyDescriptor"):
						if kd_elem.getAttribute("use") == "signing":
							for cert_elem in kd_elem.getElementsByTagName("X509Certificate"):
								certs.add(cert_elem.firstChild.data)
			if not certs:
				raise TokenValidationError("Could not find certificate in federation metadata:\n{}".format(_discard_garbage(fed.text)))
			return certs

		def _new_cryptography_checks(client_id, tenant_id, id_token):
			# check JWT validity, incl. signature
			log_p("AzureAuth._new_cryptography_checks() Running new cryptography checks incl signature verification.")
			azure_certs = list(_get_azure_certs(tenant_id))
			verified = False
			jwt_exceptions = list()
			for cert_str in azure_certs:
				cert_der = base64.b64decode(cert_str)
				x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, cert_der)
				x509_pem = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, x509)
				cert_obj = load_pem_x509_certificate(x509_pem, default_backend())
				public_key = cert_obj.public_key()
				try:
					jwt.decode(
						id_token,
						public_key,
						algorithms=["RS256"],
						options={"verify_iss": True, "verify_aud": True},
						audience=client_id,
						issuer=oauth2_token_issuer.format(tenant_id=tenant_id),
						leeway=120)
					verified = True
					break
				except jwt.InvalidTokenError as e:  # all jwt exceptions inherit from jwt.InvalidTokenError
					jwt_exceptions.append(e)
			if not verified:
				raise TokenValidationError("JWT verification error(s): {}\nID token: {}".format(" ".join(map(str, jwt_exceptions)), id_token))
			log_p("AzureAuth._new_cryptography_checks() Verified ID token.")

		# get the tenant ID from the id token
		_, body, _ = _parse_token(id_token)
		tenant_id = body['tid']
		client_id, _ = AzureAuth.load_azure_ids()
		nonce_old = AzureAuth.load_tokens()["nonce"]
		if not body["nonce"] == nonce_old:
			raise TokenValidationError("Stored ({}) and received ({}) nonce of token do not match. ID token: '{}'.".format(nonce_old, body["nonce"], id_token))
		# check validity of token
		_new_cryptography_checks(client_id, tenant_id, id_token)
		AzureAuth.store_azure_ids(client_id, tenant_id)
		return tenant_id

	def retrieve_access_token(self):
		assertion = self._get_client_assertion()

		post_form = {
			'resource': resource_url,
			'client_id': self.client_id,
			'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
			'client_assertion': assertion,
			'grant_type': 'client_credentials',
			'redirect_uri': REDIRECT_URI,
			'scope': SCOPE
		}
		url = oauth2_token_url.format(tenant_id=self.tenant_id)

		log_a("AzureAuth.retrieve_access_token() POST to URL={} with data={}".format(url, post_form))
		response = requests.post(url, data=post_form, verify=True)
		if response.status_code != 200:
			log_e("AzureAuth.retrieve_access_token() Error retrieving token (status {}), response: {}".format(response.status_code, response.__dict__))
			raise TokenError(response)
		at = response.json
		if callable(at):  # requests version compatibility
			at = at()
		log_a("AzureAuth.retrieve_access_token() response: {}".format(at))
		if "access_token" in at and at["access_token"]:
			self._access_token = at["access_token"]
			self._access_token_exp_at = datetime.datetime.fromtimestamp(int(at["expires_on"]))
			AzureAuth.store_tokens(access_token=at["access_token"], access_token_exp_at=at["expires_on"])
			return at["access_token"]
		else:
			raise TokenError(response.json())

	def _get_client_assertion(self):
		@run_as_root
		def _load_certificate_fingerprint():
			with open(SSL_CERT_FP, "r") as f:
				fp = f.read()
			return fp.strip()

		def _get_assertion_blob(header, payload):
			header_string = json.dumps(header).encode('utf-8')
			encoded_header = base64.urlsafe_b64encode(header_string).decode('utf-8').strip('=')
			payload_string = json.dumps(payload).encode('utf-8')
			encoded_payload = base64.urlsafe_b64encode(payload_string).decode('utf-8').strip('=')
			return '{0}.{1}'.format(encoded_header, encoded_payload)  # <base64-encoded-header>.<base64-encoded-payload>

		@run_as_root
		def _get_key_file_data():
			with open(SSL_KEY, "rb") as pem_file:
				key_data = pem_file.read()
			return key_data

		def _get_signature(message):
			key_data = _get_key_file_data()

			priv_key = rsa.PrivateKey.load_pkcs1(key_data)
			_signature = rsa.sign(message.encode('utf-8'), priv_key, 'SHA-256')
			encoded_signature = base64.urlsafe_b64encode(_signature)
			encoded_signature_string = encoded_signature.decode('utf-8').strip('=')
			return encoded_signature_string

		client_assertion_header = {
			'alg': 'RS256',
			'x5t': _load_certificate_fingerprint(),
		}

		# thanks to Vittorio Bertocci for this:
		# http://www.cloudidentity.com/blog/2015/02/06/requesting-an-aad-token-with-a-certificate-without-adal/
		not_before = int(time.time()) - 300  # -5min to allow time deff between the us and server
		exp_time = int(time.time()) + 600  # 10min
		client_assertion_payload = {
			'sub': self.client_id,
			'iss': self.client_id,
			'jti': str(uuid.uuid4()),
			'exp': exp_time,
			'nbf': not_before,
			'aud': oauth2_token_url.format(tenant_id=self.tenant_id)
		}

		assertion_blob = _get_assertion_blob(client_assertion_header, client_assertion_payload)
		signature = _get_signature(assertion_blob)

		# <base64-encoded-header>.<base64-encoded-payload>.<base64-encoded-signature>
		client_assertion = '{0}.{1}'.format(assertion_blob, signature)

		return client_assertion
