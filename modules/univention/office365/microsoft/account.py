# -*- coding: utf-8 -*-
#
# Univention Office 365 - account
#
# Copyright 2016-2022 Univention GmbH
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


import base64
import json
import os
import pwd
import shutil
import sys
import time
import traceback
import uuid

import six
from six.moves import UserDict
from stat import S_IRUSR, S_IWUSR
from xml.dom.minidom import parseString

import rsa
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend
import jwt

from typing import Dict, Union, Set

import requests
from requests import RequestException
from six import reraise
from six.moves.urllib.parse import urlencode
import OpenSSL.crypto

from univention.office365.microsoft import OFFICE365_API_PATH
from univention.office365.microsoft.exceptions.login_exceptions import TokenValidationError, ADConnectionIDError, NoIDsStored, WriteScriptError
from univention.office365.microsoft.manifest import Manifest
from univention.office365.microsoft.token import Token
from univention.office365.microsoft.urls import URLs
from univention.office365.microsoft.jsonstorage import JsonStorage
from univention.lib.i18n import Translation
from univention.office365.logging2udebug import get_logger
from univention.office365.ucr_helper import UCRHelper

_ = Translation('univention-management-console-module-office365').translate

SCOPE = ["Directory.ReadWrite.All"]  # https://msdn.microsoft.com/Library/Azure/Ad/Graph/howto/azure-ad-graph-api-permission-scopes#DirectoryRWDetail
SAML_SETUP_SCRIPT_CERT_PATH = "/etc/simplesamlphp/ucs-sso.{domainname}-idp-certificate{adconnection_alias}.crt"
SAML_SETUP_SCRIPT_PATH = "/var/lib/univention-office365/saml_setup{adconnection_alias}.bat"

oauth2_auth_url = "https://login.microsoftonline.com/{adconnection}/oauth2/authorize?{params}"
oauth2_token_url = "https://login.microsoftonline.com/{adconnection_id}/oauth2/token"
oauth2_token_issuer = "https://sts.windows.net/{adconnection_id}/"
federation_metadata_url = "https://login.microsoftonline.com/{adconnection_id}/federationmetadata/2007-06/federationmetadata.xml"


class AzureAccount(UserDict):
	config_base_path = OFFICE365_API_PATH

	def __init__(self, alias, config_base_path=OFFICE365_API_PATH, logger=None, lazy_load=False):
		# type: (str, str, "logging.Logger", bool) -> None
		if six.PY2:
			UserDict.__init__(self)
		else:
			super(AzureAccount, self).__init__()
		self.logger = logger or get_logger("office365", "o365")
		if alias is None:
			self.logger.error("get_conf_path called with None in alias argument")
			for line_traceback in traceback.format_stack(limit=10):
				self.logger.error(line_traceback)
			if UCRHelper.adconnection_wizard() is None:
				extra_info = _('The reason might be that the Univention Configuration Registry variable {ucr_wizard} is not set.\n'
							   'If it\'s not, you can set to the default value "{ad_default}"\n'
							   'Command to check: ucr get {ucr_wizard}\n'
							   'Command to set: "ucr set {ucr_wizard}={ad_default}"').format(ucr_wizard=UCRHelper.adconnection_wizard_ucrv, ad_default=UCRHelper.default_adconnection_name)
			else:
				extra_info = _('The reason might be that the Univention Configuration Registry variable {ucr_wizard} is set to "{ucr_wizard_value}".\n').format(ucr_wizard=UCRHelper.adconnection_wizard_ucrv, ucr_wizard_value=UCRHelper.adconnection_wizard())
			raise ValueError(_('No AD connection alias specified\n') + extra_info)
		self.alias = alias
		self.config_base_path = config_base_path or self.config_base_path
		self.__token = None
		self._access_token = None
		self.renewing = False
		conf_dir = os.path.join(config_base_path, alias)
		self.conf_dirs = {
			'CONFDIR': conf_dir,
			'SSL_KEY': os.path.join(conf_dir, "key.pem"),
			'SSL_CERT': os.path.join(conf_dir, "cert.pem"),
			'SSL_CERT_FP': os.path.join(conf_dir, "cert.fp"),
			'IDS_FILE': os.path.join(conf_dir, "ids.json"),
			'TOKEN_FILE': os.path.join(conf_dir, "token.json"),
			'MANIFEST_FILE': os.path.join(conf_dir, "manifest.json"),
		}
		if not lazy_load:
			self.load_ids_from_file()

	@property
	def token(self):
		# type: () -> Token
		if self.__token is None:
			self.__token = Token(self.alias, self.config_base_path)
		return self.__token

	@token.setter
	def token(self, token):
		# type: (Token) -> None
		self.__token = token

	def update_and_save_token(self, result):
		# type: (Dict) -> None
		self.token.update_and_save(result)

	def check_token(self):
		# type: () -> bool
		return self.token.check_token()

	def load_ids_from_file(self):
		# type: () -> None
		"""
		The Microsoft 365 Configuration Wizard places configuration files under
		/etc/univention-office365. In these we find all necessary data to
		create an access_token, which can then be used to access graph
		endpoints of both types Graph and Azure. The naming of some IDs has
		changed however and this helper function is there, so that it becomes
		obvious in which file which IDs can be found and how they were called
		in the past and how they are called now.
		"""
		ids_json = JsonStorage(self.conf_dirs["IDS_FILE"]).read()
		# TODO: remove this when the old API is not mantained anymore
		# TODO: add to migration script
		if "client_id" in ids_json:
			ids_json['application_id'] = ids_json['client_id']  # name has changed with graph!
		if "adconnection_id" in ids_json:
			ids_json['directory_id'] = ids_json['adconnection_id']  # also known as 'tenant id'
		self.update(ids_json)

	@staticmethod
	def _get_client_assertion(oauth_token_endpoint, ssl_fingerprint, key_data, application_id):
		# type: (str, str, str, str) -> str
		def _get_assertion_blob(header, payload):
			# type: (Dict, Dict) -> str
			header_string = json.dumps(header).encode('utf-8')
			encoded_header = base64.urlsafe_b64encode(header_string).decode('utf-8').strip('=')
			payload_string = json.dumps(payload).encode('utf-8')
			encoded_payload = base64.urlsafe_b64encode(payload_string).decode('utf-8').strip('=')
			return '{0}.{1}'.format(encoded_header, encoded_payload)  # <base64-encoded-header>.<base64-encoded-payload>

		def _get_signature(message, key_data):
			# type: (str, Union[bytes, str]) -> str
			priv_key = rsa.PrivateKey.load_pkcs1(key_data)
			_signature = rsa.sign(message.encode('utf-8'), priv_key, 'SHA-256')
			encoded_signature = base64.urlsafe_b64encode(_signature)
			encoded_signature_string = encoded_signature.decode('utf-8').strip('=')
			return encoded_signature_string

		client_assertion_header = {'alg': 'RS256', 'x5t': ssl_fingerprint, }

		# thanks to Vittorio Bertocci for this:
		# http://www.cloudidentity.com/blog/2015/02/06/requesting-an-aad-token-with-a-certificate-without-adal/
		not_before = int(time.time()) - 300  # -5min to allow time diff between us and the server
		exp_time = int(time.time()) + 600  # 10min
		client_assertion_payload = {'sub': application_id, 'iss': application_id, 'jti': str(uuid.uuid4()), 'exp': exp_time, 'nbf': not_before, 'aud': oauth_token_endpoint}

		assertion_blob = _get_assertion_blob(client_assertion_header, client_assertion_payload)
		signature = _get_signature(assertion_blob, key_data)

		# <base64-encoded-header>.<base64-encoded-payload>.<base64-encoded-signature>
		client_assertion = '{0}.{1}'.format(assertion_blob, signature)

		return client_assertion

	def client_assertion(self, oauth_endpoint=None):
		# type: (str) -> str
		oauth_endpoint = oauth_endpoint or URLs.ms_login(self['directory_id'])
		with open(os.path.join(self.config_base_path, self.alias, "cert.fp"), 'r') as f_ssl_fingerprint, \
				open(os.path.join(self.config_base_path, self.alias, "key.pem"), 'r') as f_ssl_key:
			return self._get_client_assertion(
				oauth_endpoint,
				f_ssl_fingerprint.read(),
				f_ssl_key.read(),
				self["application_id"]
			)

	def is_initialized(self):
		# type: () -> bool
		""""""
		self.logger.debug('adconnection_alias=%r', self.alias)
		self.load_ids_from_file()
		try:
			return all([self.get(x, False) for x in ["client_id", "adconnection_id", "reply_url", "domain"]])
		except KeyError as exc:
			# self.logger.info("AzureAuth.is_initialized(%r): %r", self.alias, exc)  # TODO uncomment
			return False

	def uninitialize(self):
		# type: () -> None
		""""""
		self.logger.debug('adconnection_alias=%r', self.alias)
		JsonStorage(self.conf_dirs["IDS_FILE"]).purge()
		JsonStorage(self.conf_dirs["TOKEN_FILE"]).purge()

	def store_manifest(self, manifest):
		# type: (Manifest) -> None
		""""""
		with open(self.conf_dirs['MANIFEST_FILE'], 'w') as fd:
			json.dump(manifest.as_dict(), fd, indent=2, separators=(',', ': '), sort_keys=True)
		os.chmod(self.conf_dirs['MANIFEST_FILE'], S_IRUSR | S_IWUSR)
		self.store_ids(adconnection_alias=self.alias, client_id=manifest.app_id, adconnection_id=manifest.adconnection_id, reply_url=manifest.reply_url, domain=manifest.domain)

	def store_ids(self, **kwargs):
		# type: (Dict) -> None
		""""""
		if "adconnection_id" in kwargs:
			tid = kwargs["adconnection_id"]
			try:
				if not (tid == "common" or uuid.UUID(tid)):
					raise ValueError()
			except ValueError:
				raise ADConnectionIDError(_("ADConnection-ID '{}' has wrong format.".format(tid)))

		JsonStorage(self.conf_dirs['IDS_FILE']).write(**kwargs)
		self.update(kwargs)

	def get_domain(self):
		# type: () -> None
		""""""
		return self["domain"]

	def get_authorization_url(self):
		# type: () -> str
		""""""
		nonce = str(uuid.uuid4())
		self.token = Token(self.alias, self.config_base_path, nonce=nonce)
		self.load_ids_from_file()
		try:
			client_id = self["client_id"]
			reply_url = self["reply_url"]
		except KeyError as exc:
			reraise(NoIDsStored, NoIDsStored(_("The configuration of Azure AD connection {adconnection} is incomplete and misses some data. Please run the wizard again.").format(adconnection=self.alias), chained_exc=exc, adconnection_alias=self.alias), sys.exc_info()[2])
		adconnection = self.get("adconnection_id") or "common"
		params = {
			'client_id': client_id,
			'redirect_uri': reply_url,
			'response_type': 'code id_token',
			'scope': 'openid',
			'nonce': nonce,
			'prompt': 'admin_consent',
			'response_mode': 'form_post',
			'resource': URLs.resource_url()
		}
		return oauth2_auth_url.format(adconnection=adconnection, params=urlencode(params))

	def write_saml_setup_script(self):
		# type: () -> None
		# TODO should be moved to UCRHelper and AzureAccount
		ucs_sso_fqdn = UCRHelper.get_ucs_sso_fqdn()
		cert = ""
		try:
			cert_path = SAML_SETUP_SCRIPT_CERT_PATH.format(domainname=UCRHelper.get_domainname(), adconnection_alias='_{}'.format(self.alias) if self.alias else '')
			with open(UCRHelper.get_saml_certificate(default=cert_path), 'rb') as fd:
				raw_cert = fd.read()
		except IOError as exc:
			self.logger.exception("while reading certificate: %s", exc)
			raise WriteScriptError(_("Error reading identity provider certificate."), adconnection_alias=self.alias)

		try:
			cert = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, raw_cert)).decode("ASCII")
		except OpenSSL.crypto.Error as exc:
			self.logger.exception("while converting certificate: %s", exc)
			raise WriteScriptError(_("Error converting identity provider certificate."), adconnection_alias=self.alias)

		saml_uri_supplement = ""
		if self.alias != UCRHelper.default_adconnection_name:
			saml_uri_supplement = '/%s' % self.alias

		issuer = 'https://{ssohost}/simplesamlphp{supplement}/saml2/idp/metadata.php'.format(ssohost=UCRHelper.get_ssohost(), supplement=saml_uri_supplement)

		# The raw base64 encoded certificate is required
		cert = cert.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').replace('\n', '')
		template = '''
@ECHO OFF
ECHO Asking for Azure Administator credentials
powershell Connect-MsolService; Set-MsolDomainAuthentication -DomainName "{domain}" -Authentication Managed; Set-MsolDomainAuthentication -DomainName "{domain}" -FederationBrandName "UCS" -Authentication Federated -ActiveLogOnUri "https://{ucs_sso_fqdn}/simplesamlphp{supplement}/saml2/idp/SSOService.php" -PassiveLogOnUri "https://{ucs_sso_fqdn}/simplesamlphp{supplement}/saml2/idp/SSOService.php" -SigningCertificate "{cert}" -IssuerUri "{issuer}" -LogOffUri "https://{ucs_sso_fqdn}/simplesamlphp{supplement}/saml2/idp/SingleLogoutService.php?ReturnTo=/univention/" -PreferredAuthenticationProtocol SAMLP;  Get-MsolDomain
ECHO Finished single sign-on configuration change
pause
'''.format(domain=self.get_domain(), ucs_sso_fqdn=ucs_sso_fqdn, cert=cert, issuer=issuer, supplement=saml_uri_supplement)

		try:
			script_path = SAML_SETUP_SCRIPT_PATH.format(adconnection_alias='_{}'.format(self.alias) if self.alias else '')
			with open(script_path, 'w') as fd:
				fd.write(template)
			os.chmod(script_path, 0o644)
		except IOError as exc:
			self.logger.exception("while writing powershell script: %s", exc)
			raise WriteScriptError(_("Error writing SAML setup script."), adconnection_alias=self.alias)

	def _get_key_file_data(self):
		# type: () -> str
		with open(self.conf_dirs['SSL_KEY'], "rb") as pem_file:
			key_data = pem_file.read()
		return key_data

	def _load_certificate_fingerprint(self):
		# type: () -> str
		with open(self.conf_dirs['SSL_CERT_FP'], "r") as fd:
			fp = fd.read()
		return fp.strip()

	def parse_id_token(self, id_token):
		# type: (str) -> str
		# TODO check where should be implemented
		def _get_azure_certs(adconnection_id):
			# type: (str) -> Set[str]
			# there's a strange non-ascii char at the beginning of the xml doc...
			def _discard_garbage(text):
				# type: (str) -> str
				return ''.join(text.partition('<')[1:])

			# the certificates with which the tokens were signed can be downloaded from the federation metadata document
			# https://msdn.microsoft.com/en-us/library/azure/dn195592.aspx
			try:
				fed = requests.get(federation_metadata_url.format(adconnection_id=adconnection_id), proxies=URLs.proxies(self.logger))
			except RequestException as exc:
				self.logger.exception("Error downloading federation metadata.")
				reraise(TokenValidationError, TokenValidationError(_("Error downloading certificates from Azure for AD connection {adconnection}. Please run the wizard again.").format(adconnection=self.alias), chained_exc=exc, adconnection_alias=self.alias), sys.exc_info()[2])
			# the federation metadata document is a XML file
			dom_tree = parseString(_discard_garbage(fed.text))
			# the certificates we want are inside:
			# <EntityDescriptor>
			#	<RoleDescriptor xsi:type="fed:SecurityTokenServiceType">  (<- the same certificates can be found in ApplicationServiceType/SAML too)
			#		<KeyDescriptor use="signing">							(<- must be use="signing")
			#			<X509Certificate>
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
				self.logger.exception("Could not find certificate in federation metadata: %r", _discard_garbage(fed.text))
				raise TokenValidationError(_("Error reading certificates of Azure AD connection {adconnection} from Azure. Please run the wizard again.").format(adconnection=self.alias), adconnection_alias=self.alias)
			return certs

		def _new_cryptography_checks(client_id, adconnection_id, id_token):
			# type: (str, str, str) -> None
			# check JWT validity, incl. signature
			self.logger.debug("Running new cryptography checks incl signature verification.")
			azure_certs = list(_get_azure_certs(adconnection_id))
			verified = False
			jwt_exceptions = list()
			for cert_str in azure_certs:
				cert_der = base64.b64decode(cert_str)
				x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, cert_der)
				x509_pem = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, x509)
				cert_obj = load_pem_x509_certificate(x509_pem, default_backend())
				public_key = cert_obj.public_key()
				try:
					jwt.decode(id_token, public_key, algorithms=["RS256"], options={"verify_iss": True, "verify_aud": True}, audience=client_id, issuer=oauth2_token_issuer.format(adconnection_id=adconnection_id), leeway=120)
					verified = True
					break
				except jwt.InvalidTokenError as exc:  # all jwt exceptions inherit from jwt.InvalidTokenError
					jwt_exceptions.append(exc)
			if not verified:
				self.logger.error("JWT verification error(s): %s\nID token: %r", " ".join(map(str, jwt_exceptions)), id_token)
				raise TokenValidationError(_("The received token for Azure AD connection {adconnection} is not valid. Please run the wizard again.").format(adconnection=self.alias), adconnection_alias=self.alias)
			self.logger.debug("Verified ID token.")

		# get the adconnection ID from the id token
		header_, body, signature_ = Token.parse(id_token)
		adconnection_id = body['tid']
		self.load_ids_from_file()
		try:
			client_id = self["client_id"]
			reply_url = self["reply_url"]
		except KeyError as exc:
			reraise(NoIDsStored, NoIDsStored(_("The configuration of Azure AD connection {adconnection} is incomplete and misses some data. Please run the wizard again.").format(adconnection=self.alias), chained_exc=exc, adconnection_alias=self.alias), sys.exc_info()[2])

		nonce_old = self.token["nonce"]
		if not body["nonce"] == nonce_old:
			self.logger.error("Stored (%r) and received (%r) nonce of token do not match. ID token: %r.", nonce_old, body["nonce"], id_token)
			raise TokenValidationError(_("The received token for Azure AD connection {adconnection} is not valid. Please run the wizard again.").format(adconnection=self.alias), adconnection_alias=self.alias)
		# check validity of token
		_new_cryptography_checks(client_id, adconnection_id, id_token)
		self.store_ids(adconnection_alias=self.alias, client_id=client_id, adconnection_id=adconnection_id, reply_url=reply_url)
		return adconnection_id

	@classmethod
	def create_local(cls, alias):
		# type: (AzureAccount, str) -> AzureAccount
		new_account = cls(alias, lazy_load=True)
		target_path = new_account.conf_dirs['CONFDIR']
		if os.path.exists(target_path):
			new_account.logger.error('Path %s already exists, but no UCR configuration for the Azure AD connection was found.', target_path)
			return None
		# Create de needed files
		os.mkdir(target_path, 0o700)
		os.chown(target_path, pwd.getpwnam('listener').pw_uid, 0)
		for filename in ('cert.fp', 'cert.pem', 'key.pem'):
			src = os.path.join(new_account.config_base_path, filename)
			shutil.copy2(src, target_path)
			os.chown(os.path.join(target_path, filename), pwd.getpwnam('listener').pw_uid, 0)

		# update ucr with the new adconnection
		new_account.uninitialize()


