# -*- coding: utf-8 -*-
import json

from typing import Optional

from univention.office365.microsoft.exceptions.login_exceptions import ManifestError
from univention.lib.i18n import Translation

from univention.office365.logging2udebug import get_logger
from univention.office365.ucr_helper import UCRHelper

_ = Translation('univention-office365').translate


class Manifest(object):

	def __init__(self, fd, adconnection_alias, adconnection_id, domain, logger=None):
		# type: ("SupportsRead", str, str, "logging.Logger") -> None
		self.logger = logger or get_logger("office365", "o365")
		self.adconnection_id = adconnection_id
		self.adconnection_alias = adconnection_alias
		self.domain = domain
		self.logger.info('Manifest() for adconnection_alias=%r adconnection_id=%r domain=%r', self.adconnection_alias, adconnection_id, domain)
		try:
			self.manifest = json.load(fd)
			if not all([isinstance(self.manifest, dict), self.app_id, self.reply_url]):  # TODO: do schema validation
				raise ValueError()
		except ValueError:
			raise ManifestError(_('The manifest is invalid: Invalid JSON document.'))

	@property
	def app_id(self):
		# type: () -> str
		return self.manifest.get('appId')

	@property
	def reply_url(self):
		# type: () -> Optional[str]
		try:
			return self.manifest["replyUrlsWithType"][0]["url"]
		except (IndexError, KeyError):
			pass

	def as_dict(self):
		# type: () -> str
		return self.manifest.copy()

	def transform(self):
		# type: () -> None
		self.manifest["oauth2AllowImplicitFlow"] = True
		self.manifest["oauth2AllowIdTokenImplicitFlow"] = True

		permissions = {
			# Permission: Azure Active Directory Graph
				"resourceAppId": "00000003-0000-0000-c000-000000000000",
				"resourceAccess": [
					# Permission Name: Directory.ReadWrite.All, Type: Application
					{"id": "19dbc75e-c2e2-444c-a770-ec69d8559fc7", "type": "Role"},
					# Permission Name: Group.ReadWrite.All, Type: Application
					{"id": "62a82d76-70ea-41e2-9197-370581804d09", "type": "Role"},
					# Permission Name: User.ReadWrite.All, Type: Application
					{"id": "741f803b-c850-494e-b5df-cde7c675a1ca", "type": "Role"},
					# Permission Name: TeamMember.ReadWrite.All, Type: Application
					{"id": "0121dc95-1b9f-4aed-8bac-58c5ac466691", "type": "Role"}]}

		for access in self.manifest['requiredResourceAccess']:
			if permissions["resourceAppId"] == access['resourceAppId']:
				# append permissions without duplicates
				[access["resourceAccess"].append(p) for p in permissions["resourceAccess"] if p not in access["resourceAccess"]]
				break
		else:
			self.manifest['requiredResourceAccess'].append(permissions)

