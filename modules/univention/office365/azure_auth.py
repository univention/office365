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
import uuid
import time
import rsa
import os
import datetime
import sys
from xml.dom.minidom import parseString
from stat import S_IRUSR, S_IWUSR
import operator
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend
import OpenSSL.crypto
import jwt
from requests.exceptions import RequestException

from univention.lib.i18n import Translation
from univention.office365.logging2udebug import get_logger
from univention.config_registry.frontend import ucr_update


_ = Translation('univention-office365').translate

NAME = "office365"
CONFDIR = "/etc/univention-office365"
SSL_KEY = os.path.join(CONFDIR, "key.pem")
SSL_CERT = os.path.join(CONFDIR, "cert.pem")
SSL_CERT_FP = os.path.join(CONFDIR, "cert.fp")
IDS_FILE = os.path.join(CONFDIR, "ids.json")
TOKEN_FILE = os.path.join(CONFDIR, "token.json")
MANIFEST_FILE = os.path.join(CONFDIR, "manifest.json")
SCOPE = ["Directory.ReadWrite.All"]  # https://msdn.microsoft.com/Library/Azure/Ad/Graph/howto/azure-ad-graph-api-permission-scopes#DirectoryRWDetail
DEBUG_FORMAT = '%(asctime)s %(levelname)-8s %(module)s.%(funcName)s:%(lineno)d  %(message)s'
LOG_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
SAML_SETUP_SCRIPT_CERT_PATH = "/etc/simplesamlphp/ucs-sso.{domainname}-idp-certificate.crt"
SAML_SETUP_SCRIPT_PATH = "/var/lib/univention-office365/saml_setup.bat"


oauth2_auth_url = "https://login.microsoftonline.com/{tenant}/oauth2/authorize?{params}"
oauth2_token_url = "https://login.microsoftonline.com/{tenant_id}/oauth2/token"
oauth2_token_issuer = "https://sts.windows.net/{tenant_id}/"
federation_metadata_url = "https://login.microsoftonline.com/{tenant_id}/federationmetadata/2007-06/federationmetadata.xml"
resource_url = "https://graph.windows.net"

logger = get_logger("office365", "o365")


class AzureError(Exception):
	def __init__(self, msg, chained_exc=None, *args, **kwargs):
		self.chained_exc = chained_exc
		super(AzureError, self).__init__(msg, *args, **kwargs)


class TokenError(AzureError):
	def __init__(self, msg, response=None, *args, **kwargs):
		self.response = response
		if response and hasattr(response, "json"):
			j = response.json
			if callable(response.json):  # requests version compatibility
				j = j()
			self.error_description = j["error_description"]
		super(TokenError, self).__init__(msg, *args, **kwargs)


class IDTokenError(AzureError):
	pass


class TokenValidationError(AzureError):
	pass


class NoIDsStored(AzureError):
	pass


class ManifestError(AzureError):
	pass


class WriteScriptError(AzureError):
	pass


class TenantIDError(AzureError):
	pass


class Manifest(object):

	@property
	def app_id(self):
		return self.manifest.get('appId')

	@property
	def reply_url(self):
		try:
			return self.manifest["replyUrls"][0]
		except (IndexError, KeyError):
			pass

	def __init__(self, fd, tenant_id, domain):
		self.tenant_id = tenant_id
		self.domain = domain
		try:
			self.manifest = json.load(fd)
			if not all([isinstance(self.manifest, dict), self.app_id, self.reply_url]):  # TODO: do schema validation
				raise ValueError()
		except ValueError:
			raise ManifestError(_('The manifest is invalid: Invalid JSON document.'))

	def as_dict(self):
		return self.manifest.copy()

	def transform(self):
		try:
			with open("/etc/univention-office365/cert.pem", "rb") as fd:
				cert = fd.read()
			with open("/etc/univention-office365/cert.fp", "rb") as fd:
				cert_fp = fd.read().strip()
		except (OSError, IOError):
			raise ManifestError(_('Could not read certificate. Please make sure the joinscript'
				' 40univention-office365.inst is executed successfully or execute it again.'))

		if cert_fp not in map(operator.itemgetter("customKeyIdentifier"), self.manifest["keyCredentials"]):
			in_key = False
			cert_key = list()
			for num, line in enumerate(cert.split("\n")):
				if line == "-----BEGIN CERTIFICATE-----":
					in_key = True
					continue
				elif line == "-----END CERTIFICATE-----":
					break
				if in_key:
					cert_key.append(line)
			key = "".join(cert_key)

			keyCredentials = dict(
				customKeyIdentifier=cert_fp,
				keyId=str(uuid.uuid4()),
				type="AsymmetricX509Cert",
				usage="verify",
				value=key)

			logger.info("Manifest.transform(): added key to manifest: fp=%r id=%r", cert_fp, keyCredentials["keyId"])

			self.manifest["keyCredentials"].append(keyCredentials)
		self.manifest["oauth2AllowImplicitFlow"] = True

		permission = {"id": "78c8a3c8-a07e-4b9e-af1b-b5ccab50a175", "type": "Role"}
		if not self.manifest["requiredResourceAccess"][0]["resourceAccess"].count(permission):
			self.manifest["requiredResourceAccess"][0]["resourceAccess"].append(permission)


class JsonStorage(object):

	def __init__(self, filename):
		self.filename = filename

	def read(self):
		try:
			with open(self.filename, "r") as fd:
				data = json.load(fd)
		except (IOError, ValueError):
			data = dict()
		if not isinstance(data, dict):
			logger.error("AzureAuth._load_data(): Expected dict in file %r, got %r.", self.filename, data)
			data = dict()
		return data

	def write(self, **kwargs):
		data = self.read()
		data.update(kwargs)
		self._save(data)

	def purge(self):
		self._save({})

	def _save(self, data):
		open(self.filename, "w").close()  # touch
		os.chmod(self.filename, S_IRUSR | S_IWUSR)
		with open(self.filename, "wb") as fd:
			json.dump(data, fd)


class AzureAuth(object):

	def __init__(self, name):
		global NAME
		NAME = name

		ids = self.load_azure_ids()
		try:
			self.client_id = ids["client_id"]
			self.tenant_id = ids["tenant_id"]
			self.reply_url = ids["reply_url"]
			self.domain = ids["domain"]
			if not all([self.client_id, self.tenant_id, self.reply_url, self.domain]):
				raise NoIDsStored("")
		except (KeyError, NoIDsStored) as exc:
			raise NoIDsStored, NoIDsStored(_("The configuration is incomplete and misses some data. Please run the wizard again."), chained_exc=exc), sys.exc_info()[2]
		self._access_token = None
		self._access_token_exp_at = None

	@classmethod
	def is_initialized(cls):
		try:
			tokens = cls.load_tokens()
			# Check if wizard was completed
			if "consent_given" not in tokens or not tokens["consent_given"]:
				return False

			ids = cls.load_azure_ids()
			return all([ids["client_id"], ids["tenant_id"], ids["reply_url"], ids["domain"]])
		except (NoIDsStored, KeyError) as exc:
			logger.info("AzureAuth.is_initialized(): %r", exc)
			return False

	@staticmethod
	def uninitialize():
		JsonStorage(IDS_FILE).purge()
		JsonStorage(TOKEN_FILE).purge()

	@staticmethod
	def load_azure_ids():
		return JsonStorage(IDS_FILE).read()

	@classmethod
	def store_manifest(cls, manifest):
		with open(MANIFEST_FILE, 'wb') as fd:
			json.dump(manifest.as_dict(), fd, indent=2, separators=(',', ': '), sort_keys=True)
		os.chmod(MANIFEST_FILE, S_IRUSR | S_IWUSR)
		cls.store_azure_ids(client_id=manifest.app_id, tenant_id=manifest.tenant_id, reply_url=manifest.reply_url, domain=manifest.domain)

	@staticmethod
	def store_azure_ids(**kwargs):
		if "tenant_id" in kwargs:
			tid = kwargs["tenant_id"]
			try:
				if not (tid == "common" or uuid.UUID(tid)):
					raise ValueError()
			except ValueError:
				raise TenantIDError(_("Tenant-ID '{}' has wrong format.".format(tid)))

		JsonStorage(IDS_FILE).write(**kwargs)

	@staticmethod
	def load_tokens():
		return JsonStorage(TOKEN_FILE).read()

	@staticmethod
	def store_tokens(**kwargs):
		JsonStorage(TOKEN_FILE).write(**kwargs)

	@classmethod
	def get_domain(cls):
		"""
		static method to access wizard supplied domain
		:return: str: domain name verified by MS
		"""
		ids = cls.load_azure_ids()
		return ids["domain"]

	def get_access_token(self):
		if not self._access_token:
			logger.debug("Loading token from disk...")
			tokens = self.load_tokens()
			self._access_token = tokens.get("access_token")
			self._access_token_exp_at = datetime.datetime.fromtimestamp(int(tokens.get("access_token_exp_at") or 0))
		if not self._access_token_exp_at or datetime.datetime.now() > self._access_token_exp_at:
			logger.debug("Token expired, retrieving now one from azure...")
			self._access_token = self.retrieve_access_token()
		logger.debug("Token valid until %s.", self._access_token_exp_at.isoformat())
		return self._access_token

	@classmethod
	def get_authorization_url(cls):
		nonce = str(uuid.uuid4())
		cls.store_tokens(nonce=nonce)
		ids = cls.load_azure_ids()
		try:
			client_id = ids["client_id"]
			reply_url = ids["reply_url"]
		except KeyError as exc:
			raise NoIDsStored, NoIDsStored(_("The configuration is incomplete and misses some data. Please run the wizard again."), chained_exc=exc), sys.exc_info()[2]
		tenant = ids.get("tenant_id") or "common"
		params = {
			'client_id': client_id,
			'redirect_uri': reply_url,
			'response_type': 'code id_token',
			'scope': 'openid',
			'nonce': nonce,
			'prompt': 'admin_consent',
			'response_mode': 'form_post',
			'resource': resource_url,
		}
		return oauth2_auth_url.format(tenant=tenant, params=urlencode(params))

	@classmethod
	def parse_id_token(cls, id_token):
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
			except (AttributeError, TypeError, ValueError) as exc:
				if sys.version_info < (3,):
					et = unicode(encoded_token, 'utf8')
				else:
					et = encoded_token
				logger.exception(u"Invalid token value: %r", et)
				raise IDTokenError, IDTokenError(_("Error reading token received from Azure. Please run the wizard again."), chained_exc=exc), sys.exc_info()[2]

		def _get_azure_certs(tenant_id):
			# there's a strange non-ascii char at the beginning of the xml doc...
			def _discard_garbage(text):
				return ''.join(text.partition('<')[1:])
			# the certificates with which the tokens were signed can be downloaded from the federation metadata document
			# https://msdn.microsoft.com/en-us/library/azure/dn195592.aspx
			try:
				fed = requests.get(federation_metadata_url.format(tenant_id=tenant_id))
			except RequestException as exc:
				logger.exception("Error downloading federation metadata.")
				raise TokenValidationError, TokenValidationError(_("Error downloading certificates from Azure. Please run the wizard again."), chained_exc=exc), sys.exc_info()[2]
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
				logger.exception("Could not find certificate in federation metadata: %r", _discard_garbage(fed.text))
				raise TokenValidationError(_("Error reading certificates from Azure. Please run the wizard again."))
			return certs

		def _new_cryptography_checks(client_id, tenant_id, id_token):
			# check JWT validity, incl. signature
			logger.debug("Running new cryptography checks incl signature verification.")
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
				except jwt.InvalidTokenError as exc:  # all jwt exceptions inherit from jwt.InvalidTokenError
					jwt_exceptions.append(exc)
			if not verified:
				logger.error("JWT verification error(s): %s\nID token: %r",
					" ".join(map(str, jwt_exceptions)), id_token)
				raise TokenValidationError(_("The received token is not valid. Please run the wizard again."))
			logger.debug("Verified ID token.")

		# get the tenant ID from the id token
		header_, body, signature_ = _parse_token(id_token)
		tenant_id = body['tid']
		ids = cls.load_azure_ids()
		try:
			client_id = ids["client_id"]
			reply_url = ids["reply_url"]
		except KeyError as exc:
			raise NoIDsStored, NoIDsStored(_("The configuration is incomplete and misses some data. Please run the wizard again."), chained_exc=exc), sys.exc_info()[2]

		nonce_old = cls.load_tokens()["nonce"]
		if not body["nonce"] == nonce_old:
			logger.error("Stored (%r) and received (%r) nonce of token do not match. ID token: %r.",
				nonce_old, body["nonce"], id_token)
			raise TokenValidationError(_("The received token is not valid. Please run the wizard again."))
		# check validity of token
		_new_cryptography_checks(client_id, tenant_id, id_token)
		cls.store_azure_ids(client_id=client_id, tenant_id=tenant_id, reply_url=reply_url)
		return tenant_id

	def retrieve_access_token(self):
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
		url = oauth2_token_url.format(tenant_id=self.tenant_id)

		logger.debug("POST to URL=%r with data=%r", url, post_form)
		response = requests.post(url, data=post_form, verify=True)
		if response.status_code != 200:
			logger.exception("Error retrieving token (status %r), response: %r", response.status_code,
				response.__dict__)
			raise TokenError(_("Error retrieving authentication token from Azure."), response=response)
		at = response.json
		if callable(at):  # requests version compatibility
			at = at()
		logger.debug("response: %r", at)
		if "access_token" in at and at["access_token"]:
			self._access_token = at["access_token"]
			self._access_token_exp_at = datetime.datetime.fromtimestamp(int(at["expires_on"]))
			self.store_tokens(access_token=at["access_token"], access_token_exp_at=at["expires_on"])
			return at["access_token"]
		else:
			logger.exception("Response didn't contain an access_token. response: %r", response)
			raise TokenError(_("Error retrieving authentication token from Azure."), response=response)

	def _get_client_assertion(self):
		def _load_certificate_fingerprint():
			with open(SSL_CERT_FP, "r") as fd:
				fp = fd.read()
			return fp.strip()

		def _get_assertion_blob(header, payload):
			header_string = json.dumps(header).encode('utf-8')
			encoded_header = base64.urlsafe_b64encode(header_string).decode('utf-8').strip('=')
			payload_string = json.dumps(payload).encode('utf-8')
			encoded_payload = base64.urlsafe_b64encode(payload_string).decode('utf-8').strip('=')
			return '{0}.{1}'.format(encoded_header, encoded_payload)  # <base64-encoded-header>.<base64-encoded-payload>

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

	@classmethod
	def write_saml_setup_script(cls):
		from univention.config_registry import ConfigRegistry
		ucr = ConfigRegistry()
		ucr.load()

		issuer = ucr.get('umc/saml/idp-server', 'https://ucs-sso.ucs.local/simplesamlphp/saml2/idp/metadata.php')
		ucs_sso_fqdn = ucr.get('ucs/server/sso/fqdn', "%s.%s" % (ucr.get('hostname', 'undefined'), ucr.get('domainname', 'undefined')))
		cert = ""
		try:
			with open(ucr.get('saml/idp/certificate/certificate', SAML_SETUP_SCRIPT_CERT_PATH.format(domainname=ucr.get('domainname', 'undefined'))), 'rb') as fd:
				raw_cert = fd.read()
		except IOError as exc:
			logger.exception("while reading certificate: %s", exc)
			raise WriteScriptError(_("Error reading identity provider certificate."))

		try:
			cert = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, raw_cert))
		except OpenSSL.crypto.Error as exc:
			logger.exception("while converting certificate: %s", exc)
			raise WriteScriptError(_("Error converting identity provider certificate."))

		# The raw base64 encoded certificate is required
		cert = cert.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').replace('\n', '')
		template = '''
@ECHO OFF
ECHO Asking for Azure Administator credentials
powershell Connect-MsolService; Set-MsolDomainAuthentication -DomainName "{domain}" -Authentication Managed; Set-MsolDomainAuthentication -DomainName "{domain}" -FederationBrandName "UCS" -Authentication Federated -ActiveLogOnUri "https://{ucs_sso_fqdn}/simplesamlphp/saml2/idp/SSOService.php" -PassiveLogOnUri "https://{ucs_sso_fqdn}/simplesamlphp/saml2/idp/SSOService.php" -SigningCertificate "{cert}" -IssuerUri "{issuer}" -LogOffUri "https://{ucs_sso_fqdn}/simplesamlphp/saml2/idp/SingleLogoutService.php?ReturnTo=/univention/" -PreferredAuthenticationProtocol SAMLP;  Get-MsolDomain
ECHO Finished single sign-on configuration change
pause
'''.format(domain=cls.get_domain(), ucs_sso_fqdn=ucs_sso_fqdn, cert=cert, issuer=issuer)

		try:
			with open(SAML_SETUP_SCRIPT_PATH, 'wb') as fd:
				fd.write(template)
			os.chmod(SAML_SETUP_SCRIPT_PATH, 0644)
		except IOError as exc:
			logger.exception("while writing powershell script: %s", exc)
			raise WriteScriptError(_("Error writing SAML setup script."))

	@classmethod
	def set_ucs_overview_link(cls):
		from univention.config_registry import ConfigRegistry
		ucr = ConfigRegistry()
		ucr.load()

		sp_query_string = "?spentityid=urn:federation:MicrosoftOnline"
		sp_link = "https://{}/simplesamlphp/saml2/idp/SSOService.php{}".format(
		ucr["ucs/server/sso/fqdn"], sp_query_string)
		ucr_update(ucr, {
		"ucs/web/overview/entries/service/office365/description": "Single Sign-On login for Microsoft Office 365",
		"ucs/web/overview/entries/service/office365/label": "Office 365 Login",
		"ucs/web/overview/entries/service/office365/link": sp_link,
		"ucs/web/overview/entries/service/office365/description/de": "Single-Sign-On Link für Microsoft Office 365",
		"ucs/web/overview/entries/service/office365/label/de": "Office 365 Login",
		"ucs/web/overview/entries/service/office365/priority": "50",
		"ucs/web/overview/entries/service/office365/icon": "/office365.png"
		})
