#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Office 365 - handle Azure oauth calls
#
# Copyright 2016-2021 Univention GmbH
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

import re
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
import pwd
from xml.dom.minidom import parseString
from stat import S_IRUSR, S_IWUSR
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend
import OpenSSL.crypto
import jwt
from requests.exceptions import RequestException
import subprocess
import shutil
import traceback

from univention.lib.i18n import Translation
from univention.office365.logging2udebug import get_logger
from univention.office365.udm_helper import UDMHelper
from univention.config_registry.frontend import ucr_update
from univention.config_registry import ConfigRegistry, handler_set, handler_unset
from univention.office365.api_helper import get_http_proxies
from univention.office365.certificate_helper import get_client_assertion


_ = Translation('univention-office365').translate

NAME = "office365"
SCOPE = ["Directory.ReadWrite.All"]  # https://msdn.microsoft.com/Library/Azure/Ad/Graph/howto/azure-ad-graph-api-permission-scopes#DirectoryRWDetail
DEBUG_FORMAT = '%(asctime)s %(levelname)-8s %(module)s.%(funcName)s:%(lineno)d  %(message)s'
LOG_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
SAML_SETUP_SCRIPT_CERT_PATH = "/etc/simplesamlphp/ucs-sso.{domainname}-idp-certificate{adconnection_alias}.crt"
SAML_SETUP_SCRIPT_PATH = "/var/lib/univention-office365/saml_setup{adconnection_alias}.bat"
ADCONNECTION_CONF_BASEPATH = "/etc/univention-office365"

oauth2_auth_url = "https://login.microsoftonline.com/{adconnection}/oauth2/authorize?{params}"
oauth2_token_url = "https://login.microsoftonline.com/{adconnection_id}/oauth2/token"
oauth2_token_issuer = "https://sts.windows.net/{adconnection_id}/"
federation_metadata_url = "https://login.microsoftonline.com/{adconnection_id}/federationmetadata/2007-06/federationmetadata.xml"
resource_url = "https://graph.windows.net"

adconnection_alias_ucrv = 'office365/adconnection/alias/'
adconnection_wizard_ucrv = 'office365/adconnection/wizard'
default_adconnection_alias_ucrv = 'office365/defaultalias'
default_adconnection_name = "defaultADconnection"

ucr = ConfigRegistry()
ucr.load()
logger = get_logger("office365", "o365")


class AzureADConnectionHandler(object):
	def __init__(self):
		self.adconnection = None

	@classmethod
	def listener_restart(cls):
		logger.info('Restarting univention-directory-listener service')
		subprocess.call(['systemctl', 'restart', 'univention-directory-listener'])

	@classmethod
	def get_conf_path(cls, name, adconnection_alias):
		if adconnection_alias is None:
			logger.error("get_conf_path called with None in adconnection_alias argument")
			for line_traceback in traceback.format_stack(limit=10):
				logger.error(line_traceback)
			raise ValueError('adconnection_alias can\'t be None')

		conf_dir = os.path.join(ADCONNECTION_CONF_BASEPATH, adconnection_alias)
		if not os.path.exists(conf_dir):
			logger.error('Config directory for Azure AD connection %s not found (%s)', adconnection_alias, conf_dir)
			return None
		return {
			'CONFDIR': conf_dir,
			'SSL_KEY': os.path.join(conf_dir, "key.pem"),
			'SSL_CERT': os.path.join(conf_dir, "cert.pem"),
			'SSL_CERT_FP': os.path.join(conf_dir, "cert.fp"),
			'IDS_FILE': os.path.join(conf_dir, "ids.json"),
			'TOKEN_FILE': os.path.join(conf_dir, "token.json"),
			'MANIFEST_FILE': os.path.join(conf_dir, "manifest.json"),
		}[name]

	@classmethod
	def get_adconnection_aliases(cls):
		res = dict()
		ucr.load()
		for k, v in ucr.items():
			if k.startswith(adconnection_alias_ucrv):
				res[k[len(adconnection_alias_ucrv):]] = v
		return res

	@classmethod
	def adconnection_id_to_alias(cls, adconnection_id):
		for alias, t_id in cls.get_adconnection_aliases().items():
			if t_id == adconnection_id:
				return alias
		logger.error('Unknown Azure AD connection ID %r.', adconnection_id)
		return None

	@classmethod
	def get_adconnections(cls, only_initialized=False):
		res = []
		aliases = cls.get_adconnection_aliases().items()
		for alias, adconnection_id in aliases:
			confdir = cls.get_conf_path('CONFDIR', alias)
			initialized = AzureAuth.is_initialized(alias)
			status = 'initialized' if initialized else 'uninitialized'
			if (only_initialized is False or initialized):
				res.append((alias, status, confdir))
		return res

	@classmethod
	def configure_wizard_for_adconnection(cls, adconnection_alias):
		# configure UCR to let wizard configure this adconnection
		# TODO: Should be removed in the future, as the wizard should be able to configure
		# adconnections by itself
		ucrv_set = '{}={}'.format(adconnection_wizard_ucrv, adconnection_alias)
		handler_set([ucrv_set])
		subprocess.call(['pkill', '-f', '/usr/sbin/univention-management-console-module -m office365'])

	@classmethod
	def create_new_adconnection(cls, adconnection_alias, make_default=False, description=""):
		aliases = cls.get_adconnection_aliases()
		if adconnection_alias in aliases:
			logger.error('Azure AD connection alias %s is already listed in UCR %s.', adconnection_alias, adconnection_alias_ucrv)
			return None

		target_path = os.path.join(ADCONNECTION_CONF_BASEPATH, adconnection_alias)
		if os.path.exists(target_path):
			logger.error('Path %s already exists, but no UCR configuration for the Azure AD connection was found.', target_path)
			return None

		os.mkdir(target_path, 0o700)
		os.chown(target_path, pwd.getpwnam('listener').pw_uid, 0)
		for filename in ('cert.fp', 'cert.pem', 'key.pem'):
			src = os.path.join(ADCONNECTION_CONF_BASEPATH, filename)
			shutil.copy2(src, target_path)
			os.chown(os.path.join(target_path, filename), pwd.getpwnam('listener').pw_uid, 0)

		AzureAuth.uninitialize(adconnection_alias)
		ucrv = ['{}{}=uninitialized'.format(adconnection_alias_ucrv, adconnection_alias)]
		if make_default:
			ucrv.append('{}={}'.format(default_adconnection_alias_ucrv, adconnection_alias))

		handler_set(ucrv)
		UDMHelper.create_udm_adconnection(adconnection_alias, description)
		cls.configure_wizard_for_adconnection(adconnection_alias)
		cls.listener_restart()

	@classmethod
	def rename_adconnection(cls, old_adconnection_alias, new_adconnection_alias):
		aliases = cls.get_adconnection_aliases()
		if old_adconnection_alias not in aliases:
			logger.error('Azure AD connection alias %s is not listed in UCR %s.', old_adconnection_alias, adconnection_alias_ucrv)
			return None
		if new_adconnection_alias in aliases:
			logger.error('Azure AD connection alias %s is already configured in UCR %s, cannot rename Azure AD connection %s.', new_adconnection_alias, adconnection_alias_ucrv, old_adconnection_alias)
			return None

		new_adconnection_path = os.path.join(ADCONNECTION_CONF_BASEPATH, new_adconnection_alias)
		if os.path.exists(new_adconnection_path):
			logger.error('The path for the target Azure AD connection name %s already exists, but no UCR configuration for the Azure AD connection was found.', new_adconnection_path)
			return None
		old_adconnection_path = os.path.join(ADCONNECTION_CONF_BASEPATH, old_adconnection_alias)
		if not os.path.exists(old_adconnection_path):
			logger.error('The path for the old Azure AD connection %s does not exist.', old_adconnection_path)
			return None

		shutil.move(old_adconnection_path, new_adconnection_path)
		ucrv_set = '{}={}'.format('%s%s' % (adconnection_alias_ucrv, new_adconnection_alias), ucr.get('%s%s' % (adconnection_alias_ucrv, old_adconnection_alias)))
		handler_set([ucrv_set])
		ucrv_unset = '%s%s' % (adconnection_alias_ucrv, old_adconnection_alias)
		handler_unset([ucrv_unset])
		cls.listener_restart()

	@classmethod
	def remove_adconnection(cls, adconnection_alias):
		aliases = cls.get_adconnection_aliases()
		# Checks
		if adconnection_alias not in aliases:
			logger.error('Azure AD connection alias %s is not listed in UCR %s.', adconnection_alias, adconnection_alias_ucrv)
			return None

		target_path = os.path.join(ADCONNECTION_CONF_BASEPATH, adconnection_alias)
		if not os.path.exists(target_path):
			logger.info('Configuration files for the Azure AD connection in %s do not exist. Removing Azure AD connection anyway...', target_path)

		UDMHelper.remove_udm_adconnection(adconnection_alias)
		shutil.rmtree(target_path)
		ucrv_unset = '%s%s' % (adconnection_alias_ucrv, adconnection_alias)
		handler_unset([ucrv_unset])
		cls.listener_restart()


class AzureError(Exception):
	def __init__(self, msg, chained_exc=None, adconnection_alias=None, *args, **kwargs):
		self.chained_exc = chained_exc
		self.adconnection_alias = adconnection_alias
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


class ADConnectionIDError(AzureError):
	pass


class Manifest(object):

	@property
	def app_id(self):
		return self.manifest.get('appId')

	@property
	def reply_url(self):
		try:
			return self.manifest["replyUrlsWithType"][0]["url"]
		except (IndexError, KeyError):
			pass

	def __init__(self, fd, adconnection_id, domain):
		self.adconnection_id = adconnection_id
		self.adconnection_alias = AzureADConnectionHandler.adconnection_id_to_alias(adconnection_id)
		self.domain = domain
		logger.info('Manifest() for adconnection_alias=%r adconnection_id=%r domain=%r', self.adconnection_alias, adconnection_id, domain)
		try:
			self.manifest = json.load(fd)
			if not all([isinstance(self.manifest, dict), self.app_id, self.reply_url]):  # TODO: do schema validation
				raise ValueError()
		except ValueError:
			raise ManifestError(_('The manifest is invalid: Invalid JSON document.'))

	def as_dict(self):
		return self.manifest.copy()

	def transform(self):
		self.manifest["oauth2AllowImplicitFlow"] = True
		self.manifest["oauth2AllowIdTokenImplicitFlow"] = True

		permissions = {
			# Permission: Azure Active Directory Graph
			"00000002-0000-0000-c000-000000000000": {"resourceAppId": "00000002-0000-0000-c000-000000000000",
				"resourceAccess": [
					# Permission Name: Directory.ReadWrite.All, Type: Application
					{"id": "78c8a3c8-a07e-4b9e-af1b-b5ccab50a175", "type": "Role"}]},
			# Permission: Microsoft Graph
			"00000003-0000-0000-c000-000000000000": {"resourceAppId": "00000003-0000-0000-c000-000000000000",
				"resourceAccess": [
					# Permission Name: Directory.ReadWrite.All, Type: Application
					{"id": "19dbc75e-c2e2-444c-a770-ec69d8559fc7", "type": "Role"},
					# Permission Name: Group.ReadWrite.All, Type: Application
					{"id": "62a82d76-70ea-41e2-9197-370581804d09", "type": "Role"},
					# Permission Name: User.ReadWrite.All, Type: Application
					{"id": "741f803b-c850-494e-b5df-cde7c675a1ca", "type": "Role"},
					# Permission Name: TeamMember.ReadWrite.All, Type: Application
					{"id": "0121dc95-1b9f-4aed-8bac-58c5ac466691", "type": "Role"}]}}

		apps = permissions.keys()
		for appid in permissions.keys():
			for access in self.manifest['requiredResourceAccess']:
				if appid == access['resourceAppId']:
					# append permissions without duplicates
					[access["resourceAccess"].append(p) for p in permissions[appid]["resourceAccess"] if p not in access["resourceAccess"]]
					apps.remove(appid)
		for appid in apps:
			self.manifest['requiredResourceAccess'].append(permissions[appid])


class JsonStorage(object):
	listener_uid = None

	def __init__(self, filename):
		self.filename = filename
		if not self.listener_uid:
			self.__class__.listener_uid = pwd.getpwnam('listener').pw_uid

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
		os.chown(self.filename, self.listener_uid, 0)
		os.chmod(self.filename, S_IRUSR | S_IWUSR)
		with open(self.filename, "wb") as fd:
			json.dump(data, fd)


class AzureAuth(object):
	proxies = None

	def __init__(self, name, adconnection_alias=None):
		global NAME
		NAME = name

		self.adconnection_alias = adconnection_alias
		logger.debug('adconnection_alias=%r', adconnection_alias)
		ids = self.load_azure_ids(adconnection_alias)
		try:
			self.client_id = ids["client_id"]
			self.adconnection_id = ids["adconnection_id"]
			self.reply_url = ids["reply_url"]
			self.domain = ids["domain"]
			if not all([self.client_id, self.adconnection_id, self.reply_url, self.domain]):
				raise NoIDsStored("")
		except (KeyError, NoIDsStored) as exc:
			raise NoIDsStored, NoIDsStored(_("The configuration of Azure AD connection {adconnection} is incomplete and misses some data. Please run the wizard again.").format(adconnection=adconnection_alias), chained_exc=exc), sys.exc_info()[2]
		self._access_token = None
		self._access_token_exp_at = None
		if self.proxies is None:
			self.__class__.proxies = get_http_proxies(ucr, logger)

	@classmethod
	def is_initialized(cls, adconnection_alias=None):
		logger.debug('adconnection_alias=%r', adconnection_alias)
		try:
			tokens = cls.load_tokens(adconnection_alias)
			# Check if wizard was completed
			if "consent_given" not in tokens or not tokens["consent_given"]:
				return False

			ids = cls.load_azure_ids(adconnection_alias)
			return all([ids["client_id"], ids["adconnection_id"], ids["reply_url"], ids["domain"]])
		except (NoIDsStored, KeyError) as exc:
			logger.info("AzureAuth.is_initialized(%r): %r", adconnection_alias, exc)
			return False

	@staticmethod
	def uninitialize(adconnection_alias=None):
		logger.debug('adconnection_alias=%r', adconnection_alias)
		JsonStorage(AzureADConnectionHandler.get_conf_path('IDS_FILE', adconnection_alias)).purge()
		JsonStorage(AzureADConnectionHandler.get_conf_path('TOKEN_FILE', adconnection_alias)).purge()

	@staticmethod
	def load_azure_ids(adconnection_alias=None):
		return JsonStorage(AzureADConnectionHandler.get_conf_path('IDS_FILE', adconnection_alias)).read()

	@classmethod
	def store_manifest(cls, manifest, adconnection_alias=None):
		with open(AzureADConnectionHandler.get_conf_path('MANIFEST_FILE', adconnection_alias), 'wb') as fd:
			json.dump(manifest.as_dict(), fd, indent=2, separators=(',', ': '), sort_keys=True)
		os.chmod(AzureADConnectionHandler.get_conf_path('MANIFEST_FILE', adconnection_alias), S_IRUSR | S_IWUSR)
		cls.store_azure_ids(adconnection_alias=adconnection_alias, client_id=manifest.app_id, adconnection_id=manifest.adconnection_id, reply_url=manifest.reply_url, domain=manifest.domain)

	@staticmethod
	def store_azure_ids(adconnection_alias=None, **kwargs):
		if "adconnection_id" in kwargs:
			tid = kwargs["adconnection_id"]
			try:
				if not (tid == "common" or uuid.UUID(tid)):
					raise ValueError()
			except ValueError:
				raise ADConnectionIDError(_("ADConnection-ID '{}' has wrong format.".format(tid)))

		JsonStorage(AzureADConnectionHandler.get_conf_path('IDS_FILE', adconnection_alias)).write(**kwargs)

	@staticmethod
	def load_tokens(adconnection_alias=None):
		return JsonStorage(AzureADConnectionHandler.get_conf_path('TOKEN_FILE', adconnection_alias)).read()

	@staticmethod
	def store_tokens(adconnection_alias=None, **kwargs):
		JsonStorage(AzureADConnectionHandler.get_conf_path('TOKEN_FILE', adconnection_alias)).write(**kwargs)

	@classmethod
	def get_domain(cls, adconnection_alias=None):
		"""
		static method to access wizard supplied domain
		:return: str: domain name verified by MS
		"""
		ids = cls.load_azure_ids(adconnection_alias)
		return ids["domain"]

	def get_access_token(self):
		if not self._access_token:
			logger.debug("Loading token from disk...")
			tokens = self.load_tokens(self.adconnection_alias)
			self._access_token = tokens.get("access_token")
			self._access_token_exp_at = datetime.datetime.fromtimestamp(int(tokens.get("access_token_exp_at") or 0))
		if not self._access_token_exp_at or datetime.datetime.now() > self._access_token_exp_at:
			logger.debug("Token expired, retrieving now one from azure...")
			self._access_token = self.retrieve_access_token()
		logger.debug("Token valid until %s.", self._access_token_exp_at.isoformat())
		return self._access_token

	@classmethod
	def get_authorization_url(cls, adconnection_alias=None):
		nonce = str(uuid.uuid4())
		cls.store_tokens(adconnection_alias=adconnection_alias, nonce=nonce)
		ids = cls.load_azure_ids(adconnection_alias)
		try:
			client_id = ids["client_id"]
			reply_url = ids["reply_url"]
		except KeyError as exc:
			raise NoIDsStored, NoIDsStored(_("The configuration of Azure AD connection {adconnection} is incomplete and misses some data. Please run the wizard again.").format(adconnection=adconnection_alias), chained_exc=exc, adconnection_alias=adconnection_alias), sys.exc_info()[2]
		adconnection = ids.get("adconnection_id") or "common"
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
		return oauth2_auth_url.format(adconnection=adconnection, params=urlencode(params))

	@classmethod
	def parse_id_token(cls, id_token, adconnection_alias=None):
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
				raise IDTokenError, IDTokenError(_("Error reading token of Azure AD connection {adconnection} received from Azure. Please run the wizard again.").format(adconnection=adconnection_alias), chained_exc=exc, adconnection_alias=adconnection_alias), sys.exc_info()[2]

		def _get_azure_certs(adconnection_id):
			# there's a strange non-ascii char at the beginning of the xml doc...
			def _discard_garbage(text):
				return ''.join(text.partition('<')[1:])
			# the certificates with which the tokens were signed can be downloaded from the federation metadata document
			# https://msdn.microsoft.com/en-us/library/azure/dn195592.aspx
			if cls.proxies is None:
				cls.proxies = get_http_proxies(ucr, logger)
			try:
				fed = requests.get(federation_metadata_url.format(adconnection_id=adconnection_id), proxies=cls.proxies)
			except RequestException as exc:
				logger.exception("Error downloading federation metadata.")
				raise TokenValidationError, TokenValidationError(_("Error downloading certificates from Azure for AD connection {adconnection}. Please run the wizard again.").format(adconnection=adconnection_alias), chained_exc=exc, adconnection_alias=adconnection_alias), sys.exc_info()[2]
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
				raise TokenValidationError(_("Error reading certificates of Azure AD connection {adconnection} from Azure. Please run the wizard again.").format(adconnection=adconnection_alias), adconnection_alias=adconnection_alias)
			return certs

		def _new_cryptography_checks(client_id, adconnection_id, id_token):
			# check JWT validity, incl. signature
			logger.debug("Running new cryptography checks incl signature verification.")
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
					jwt.decode(
						id_token,
						public_key,
						algorithms=["RS256"],
						options={"verify_iss": True, "verify_aud": True},
						audience=client_id,
						issuer=oauth2_token_issuer.format(adconnection_id=adconnection_id),
						leeway=120)
					verified = True
					break
				except jwt.InvalidTokenError as exc:  # all jwt exceptions inherit from jwt.InvalidTokenError
					jwt_exceptions.append(exc)
			if not verified:
				logger.error("JWT verification error(s): %s\nID token: %r", " ".join(map(str, jwt_exceptions)), id_token)
				raise TokenValidationError(_("The received token for Azure AD connection {adconnection} is not valid. Please run the wizard again.").format(adconnection=adconnection_alias), adconnection_alias=adconnection_alias)
			logger.debug("Verified ID token.")

		# get the adconnection ID from the id token
		header_, body, signature_ = _parse_token(id_token)
		adconnection_id = body['tid']
		ids = cls.load_azure_ids(adconnection_alias)
		try:
			client_id = ids["client_id"]
			reply_url = ids["reply_url"]
		except KeyError as exc:
			raise NoIDsStored, NoIDsStored(_("The configuration of Azure AD connection {adconnection} is incomplete and misses some data. Please run the wizard again.").format(adconnection=adconnection_alias), chained_exc=exc, adconnection_alias=adconnection_alias), sys.exc_info()[2]

		nonce_old = cls.load_tokens(adconnection_alias)["nonce"]
		if not body["nonce"] == nonce_old:
			logger.error("Stored (%r) and received (%r) nonce of token do not match. ID token: %r.", nonce_old, body["nonce"], id_token)
			raise TokenValidationError(_("The received token for Azure AD connection {adconnection} is not valid. Please run the wizard again.").format(adconnection=adconnection_alias), adconnection_alias=adconnection_alias)
		# check validity of token
		_new_cryptography_checks(client_id, adconnection_id, id_token)
		cls.store_azure_ids(adconnection_alias=adconnection_alias, client_id=client_id, adconnection_id=adconnection_id, reply_url=reply_url)
		return adconnection_id

	def retrieve_access_token(self):
		'''
		gets a new access token from microsoft and stores the result in a file
		named after the alias of the connection.
		'''

		assertion = get_client_assertion(
			oauth2_token_url.format(adconnection_id=self.adconnection_id),
			self._load_certificate_fingerprint(),
			self._get_key_file_data(),
			self.client_id
		)

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

	def _load_certificate_fingerprint(self):
		with open(AzureADConnectionHandler.get_conf_path('SSL_CERT_FP', self.adconnection_alias), "r") as fd:
			fp = fd.read()
		return fp.strip()

	def _get_key_file_data(self):
		with open(AzureADConnectionHandler.get_conf_path('SSL_KEY', self.adconnection_alias), "rb") as pem_file:
			key_data = pem_file.read()
		return key_data

	@classmethod
	def write_saml_setup_script(cls, adconnection_alias=None):
		from univention.config_registry import ConfigRegistry
		ucr = ConfigRegistry()
		ucr.load()

		ucs_sso_fqdn = ucr.get('ucs/server/sso/fqdn', "%s.%s" % (ucr.get('hostname', 'undefined'), ucr.get('domainname', 'undefined')))
		cert = ""
		try:
			cert_path = SAML_SETUP_SCRIPT_CERT_PATH.format(
				domainname=ucr.get('domainname', 'undefined'),
				adconnection_alias='_{}'.format(adconnection_alias) if adconnection_alias else ''
			)
			with open(ucr.get('saml/idp/certificate/certificate', cert_path), 'rb') as fd:
				raw_cert = fd.read()
		except IOError as exc:
			logger.exception("while reading certificate: %s", exc)
			raise WriteScriptError(_("Error reading identity provider certificate."), adconnection_alias=adconnection_alias)

		try:
			cert = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, raw_cert))
		except OpenSSL.crypto.Error as exc:
			logger.exception("while converting certificate: %s", exc)
			raise WriteScriptError(_("Error converting identity provider certificate."), adconnection_alias=adconnection_alias)

		saml_uri_supplement = ""
		if adconnection_alias != default_adconnection_name:
			saml_uri_supplement = '/%s' % adconnection_alias

		issuer = 'https://{ssohost}/simplesamlphp{supplement}/saml2/idp/metadata.php'.format(ssohost=ucr.get('ucs/server/sso/fqdn', 'ucs-sso.{domain}'.format(domain=ucr.get('domainname'))), supplement=saml_uri_supplement)

		# The raw base64 encoded certificate is required
		cert = cert.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').replace('\n', '')
		template = '''
@ECHO OFF
ECHO Asking for Azure Administator credentials
powershell Connect-MsolService; Set-MsolDomainAuthentication -DomainName "{domain}" -Authentication Managed; Set-MsolDomainAuthentication -DomainName "{domain}" -FederationBrandName "UCS" -Authentication Federated -ActiveLogOnUri "https://{ucs_sso_fqdn}/simplesamlphp{supplement}/saml2/idp/SSOService.php" -PassiveLogOnUri "https://{ucs_sso_fqdn}/simplesamlphp{supplement}/saml2/idp/SSOService.php" -SigningCertificate "{cert}" -IssuerUri "{issuer}" -LogOffUri "https://{ucs_sso_fqdn}/simplesamlphp{supplement}/saml2/idp/SingleLogoutService.php?ReturnTo=/univention/" -PreferredAuthenticationProtocol SAMLP;  Get-MsolDomain
ECHO Finished single sign-on configuration change
pause
'''.format(domain=cls.get_domain(adconnection_alias), ucs_sso_fqdn=ucs_sso_fqdn, cert=cert, issuer=issuer, supplement=saml_uri_supplement)

		try:
			script_path = SAML_SETUP_SCRIPT_PATH.format(adconnection_alias='_{}'.format(adconnection_alias) if adconnection_alias else '')
			with open(script_path, 'wb') as fd:
				fd.write(template)
			os.chmod(script_path, 0644)
		except IOError as exc:
			logger.exception("while writing powershell script: %s", exc)
			raise WriteScriptError(_("Error writing SAML setup script."), adconnection_alias=adconnection_alias)

	@classmethod
	def set_ucs_overview_link(cls):
		from univention.config_registry import ConfigRegistry
		ucr = ConfigRegistry()
		ucr.load()

		sp_query_string = "?spentityid=urn:federation:MicrosoftOnline"
		sp_link = "https://{}/simplesamlphp/saml2/idp/SSOService.php{}".format(ucr["ucs/server/sso/fqdn"], sp_query_string)
		ucr_update(ucr, {
			"ucs/web/overview/entries/service/office365/description": "Single Sign-On login for Microsoft 365",
			"ucs/web/overview/entries/service/office365/label": "Microsoft 365 Login",
			"ucs/web/overview/entries/service/office365/link": sp_link,
			"ucs/web/overview/entries/service/office365/description/de": "Single-Sign-On Link für Microsoft 365",
			"ucs/web/overview/entries/service/office365/label/de": "Microsoft 365 Login",
			"ucs/web/overview/entries/service/office365/priority": "50",
			"ucs/web/overview/entries/service/office365/icon": "/office365.png"
		})

# vim: filetype=python noexpandtab tabstop=4 shiftwidth=4 softtabstop=4
