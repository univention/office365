import json

from univention.office365.api.login_exceptions import ManifestError
from univention.lib.i18n import Translation

from univention.office365.logging2udebug import get_logger
from univention.office365.ucr_helper import UCRHelper

_ = Translation('univention-office365').translate


class Manifest(object):

	def __init__(self, fd, adconnection_id, domain, logger=None):
		self.logger = logger or get_logger("office365", "o365")
		self.adconnection_id = adconnection_id
		self.adconnection_alias = UCRHelper.adconnection_id_to_alias(adconnection_id)
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
		return self.manifest.get('appId')

	@property
	def reply_url(self):
		try:
			return self.manifest["replyUrlsWithType"][0]["url"]
		except (IndexError, KeyError):
			pass

	def as_dict(self):
		return self.manifest.copy()

	def transform(self):
		self.manifest["oauth2AllowImplicitFlow"] = True
		self.manifest["oauth2AllowIdTokenImplicitFlow"] = True

		permissions = {
			# Permission: Azure Active Directory Graph
			"00000002-0000-0000-c000-000000000000": {
				"resourceAppId": "00000002-0000-0000-c000-000000000000",
				"resourceAccess": [
					# Permission Name: Directory.ReadWrite.All, Type: Application
					{"id": "78c8a3c8-a07e-4b9e-af1b-b5ccab50a175", "type": "Role"}]},
			# Permission: Microsoft Graph
			"00000003-0000-0000-c000-000000000000": {
				"resourceAppId": "00000003-0000-0000-c000-000000000000",
				"resourceAccess": [
					# Permission Name: Directory.ReadWrite.All, Type: Application
					{"id": "19dbc75e-c2e2-444c-a770-ec69d8559fc7", "type": "Role"},
					# Permission Name: Group.ReadWrite.All, Type: Application
					{"id": "62a82d76-70ea-41e2-9197-370581804d09", "type": "Role"},
					# Permission Name: User.ReadWrite.All, Type: Application
					{"id": "741f803b-c850-494e-b5df-cde7c675a1ca", "type": "Role"},
					# Permission Name: TeamMember.ReadWrite.All, Type: Application
					{"id": "0121dc95-1b9f-4aed-8bac-58c5ac466691", "type": "Role"}]}}

		apps = list(permissions.keys())
		for appid in permissions.keys():
			for access in self.manifest['requiredResourceAccess']:
				if appid == access['resourceAppId']:
					# append permissions without duplicates
					[access["resourceAccess"].append(p) for p in permissions[appid]["resourceAccess"] if p not in access["resourceAccess"]]
					apps.remove(appid)
		for appid in apps:
			self.manifest['requiredResourceAccess'].append(permissions[appid])

