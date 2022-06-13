# -*- coding: utf-8 -*-
import json

from typing import Optional

from univention.office365.microsoft.exceptions.login_exceptions import ManifestError
from univention.lib.i18n import Translation

from univention.office365.logging2udebug import get_logger

_ = Translation('univention-office365').translate


class ApplicationPermissions:
	name_to_app_rol_id = {
		'CustomAuthenticationExtension.Receive.Payload': '214e810f-fda8-4fd7-a475-29461495eb00',
		'Policy.ReadWrite.AccessReview': '77c863fd-06c0-47ce-a7eb-49773e89d319',
		'Group.ReadWrite.All': '62a82d76-70ea-41e2-9197-370581804d09',
		'Group.Read.All': '5b567255-7703-4780-807c-7be8301ae99b',
		'ThreatSubmission.ReadWrite.All': 'd72bdbf4-a59b-405c-8b04-5995895819ac',
		'Bookings.Read.All': '6e98f277-b046-4193-a4f2-6bf6a78cd491',
		'BookingsAppointment.ReadWrite.All': '9769393e-5a9f-4302-9e3d-7e018ecb64a7',
		'RecordsManagement.Read.All': 'ac3a2b8e-03a3-4da9-9ce0-cbe28bf1accd',
		'RecordsManagement.ReadWrite.All': 'eb158f57-df43-4751-8b21-b8932adb3d34',
		'DelegatedAdminRelationship.Read.All': 'f6e9e124-4586-492f-adc0-c6f96e4823fd',
		'DelegatedAdminRelationship.ReadWrite.All': 'cc13eba4-8cd8-44c6-b4d4-f93237adce58',
		'RoleManagement.ReadWrite.CloudPC': '274d0592-d1b6-44bd-af1d-26d259bcb43a',
		'RoleManagement.Read.CloudPC': '031a549a-bb80-49b6-8032-2068448c6a3c',
		'CustomSecAttributeAssignment.Read.All': '3b37c5a4-1226-493d-bec3-5d6c6b866f3f',
		'CustomSecAttributeDefinition.Read.All': 'b185aa14-d8d2-42c1-a685-0f5596613624',
		'ExternalConnection.Read.All': '1914711b-a1cb-4793-b019-c2ce0ed21b8c',
		'ExternalConnection.ReadWrite.All': '34c37bc0-2b40-4d5e-85e1-2365cd256d79',
		'ExternalItem.Read.All': '7a7cffad-37d2-4f48-afa4-c6ab129adcc2',
		'Policy.ReadWrite.CrossTenantAccess': '338163d7-f101-4c92-94ba-ca46fe52447c',
		'CustomSecAttributeDefinition.ReadWrite.All': '12338004-21f4-4896-bf5e-b75dfaf1016d',
		'CustomSecAttributeAssignment.ReadWrite.All': 'de89b5e4-5b8f-48eb-8925-29c2b33bd8bd',
		'SecurityIncident.ReadWrite.All': '34bf0e97-1971-4929-b999-9e2442d941d7',
		'SecurityIncident.Read.All': '45cc0394-e837-488b-a098-1918f48d186c',
		'SecurityAlert.ReadWrite.All': 'ed4fca05-be46-441f-9803-1873825f8fdb',
		'SecurityAlert.Read.All': '472e4a4d-bb4a-4026-98d1-0b0d74cb74a5',
		'eDiscovery.ReadWrite.All': 'b2620db1-3bf7-4c5b-9cb9-576d29eac736',
		'eDiscovery.Read.All': '50180013-6191-4d1e-a373-e590ff4e66af',
		'ThreatHunting.Read.All': 'dd98c7f5-2d42-42d3-a0e4-633161547251',
		'TeamworkDevice.Read.All': '0591bafd-7c1c-4c30-a2a5-2b9aacb1dfe8',
		'TeamworkDevice.ReadWrite.All': '79c02f5b-bd4f-4713-bc2c-a8a4a66e127b',
		'IdentityRiskyServicePrincipal.ReadWrite.All': 'cb8d6980-6bcb-4507-afec-ed6de3a2d798',
		'TeamsTab.ReadWriteSelfForUser.All': '3c42dec6-49e8-4a0a-b469-36cff0d9da93',
		'TeamsTab.ReadWriteSelfForTeam.All': '91c32b81-0ef0-453f-a5c7-4ce2e562f449',
		'TeamsTab.ReadWriteSelfForChat.All': '9f62e4a2-a2d6-4350-b28b-d244728c4f86',
		'IdentityRiskyServicePrincipal.Read.All': '607c7344-0eed-41e5-823a-9695ebe1b7b0',
		'SearchConfiguration.ReadWrite.All': '0e778b85-fefa-466d-9eec-750569d92122',
		'SearchConfiguration.Read.All': 'ada977a5-b8b1-493b-9a91-66c206d76ecf',
		'OnlineMeetingArtifact.Read.All': 'df01ed3b-eb61-4eca-9965-6b3d789751b2',
		'AppCatalog.ReadWrite.All': 'dc149144-f292-421e-b185-5953f2e98d7f',
		'AppCatalog.Read.All': 'e12dae10-5a57-4817-b79d-dfbec5348930',
		'WorkforceIntegration.ReadWrite.All': '202bf709-e8e6-478e-bcfd-5d63c50b68e3',
		'Presence.ReadWrite.All': '83cded22-8297-4ff6-a7fa-e97e9545a259',
		'TeamworkTag.ReadWrite.All': 'a3371ca5-911d-46d6-901c-42c8c7a937d8',
		'TeamworkTag.Read.All': 'b74fd6c4-4bde-488e-9695-eeb100e4907f',
		'WindowsUpdates.ReadWrite.All': '7dd1be58-6e76-4401-bf8d-31d1e8180d5b',
		'ExternalConnection.ReadWrite.OwnedBy': 'f431331c-49a6-499f-be1c-62af19c34a9d',
		'ExternalItem.ReadWrite.OwnedBy': '8116ae0f-55c2-452d-9944-d18420f5b2c8',
		'Sites.Selected': '883ea226-0bf2-4a8f-9f9d-92c9162a727d',
		'Sites.Read.All': '332a536c-c7ef-4017-ab91-336970924f0d',
		'Sites.ReadWrite.All': '9492366f-7969-46a4-8d15-ed1a20078fff',
		'CloudPC.ReadWrite.All': '3b4349e1-8cf5-45a3-95b7-69d1751d3e6a',
		'CloudPC.Read.All': 'a9e09520-8ed4-4cde-838e-4fdea192c227',
		'ServicePrincipalEndpoint.ReadWrite.All': '89c8469c-83ad-45f7-8ff2-6e3d4285709e',
		'ServicePrincipalEndpoint.Read.All': '5256681e-b7f6-40c0-8447-2d9db68797a0',
		'TeamsActivity.Send': 'a267235f-af13-44dc-8385-c1dc93023186',
		'AgreementAcceptance.Read.All': 'd8e4ec18-f6c0-4620-8122-c8b1f2bf400e',
		'Agreement.ReadWrite.All': 'c9090d00-6101-42f0-a729-c41074260d47',
		'Agreement.Read.All': '2f3e6f8c-093b-4c57-a58b-ba5ce494a169',
		'ConsentRequest.ReadWrite.All': '9f1b81a7-0223-4428-bfa4-0bcb5535f27d',
		'Policy.ReadWrite.ConsentRequest': '999f8c63-0a38-4f1b-91fd-ed1947bdd1a9',
		'ConsentRequest.Read.All': '1260ad83-98fb-4785-abbb-d6cc1806fd41',
		'Mail.ReadBasic.All': '693c5e45-0940-467d-9b8a-1022fb9d42ef',
		'Mail.ReadBasic': '6be147d2-ea4f-4b5a-a3fa-3eab6f3c140a',
		'Policy.ReadWrite.FeatureRollout': '2044e4f1-e56c-435b-925c-44cd8f6ba89a',
		'RoleManagement.ReadWrite.Directory': '9e3f62cf-ca93-4989-b6ce-bf83c28f9fe8',
		'RoleManagement.Read.Directory': '483bed4a-2ad3-4361-a73b-c83ccdbdc53c',
		'Organization.ReadWrite.All': '292d869f-3427-49a8-9dab-8c70152b74e9',
		'Organization.Read.All': '498476ce-e0fe-48b0-b801-37ba7e2685c6',
		'Place.Read.All': '913b9306-0ce1-42b8-9137-6a7df690a760',
		'Member.Read.Hidden': '658aa5d8-239f-45c4-aa12-864f4fc7e490',
		'ExternalItem.ReadWrite.All': '38c3d6ee-69ee-422f-b954-e17819665354',
		'AccessReview.ReadWrite.Membership': '18228521-a591-40f1-b215-5fad4488c117',
		'DeviceManagementConfiguration.Read.All': 'dc377aa6-52d8-4e23-b271-2a7ae04cedf3',
		'DeviceManagementApps.Read.All': '7a6ee1e7-141e-4cec-ae74-d9db155731ff',
		'DeviceManagementManagedDevices.Read.All': '2f51be20-0bb4-4fed-bf7b-db946066c75e',
		'DeviceManagementRBAC.Read.All': '58ca0d9a-1575-47e1-a3cb-007ef2e4583b',
		'DeviceManagementServiceConfig.Read.All': '06a5fe6d-c49d-46a7-b082-56b1b14103c7',
		'OnPremisesPublishingProfiles.ReadWrite.All': '0b57845e-aa49-4e6f-8109-ce654fffa618',
		'TrustFrameworkKeySet.ReadWrite.All': '4a771c9a-1cf2-4609-b88e-3d3e02d539cd',
		'TrustFrameworkKeySet.Read.All': 'fff194f1-7dce-4428-8301-1badb5518201',
		'Policy.ReadWrite.TrustFramework': '79a677f7-b79d-40d0-a36a-3e6f8688dd7a',
		'Policy.Read.All': '246dd0d5-5bd0-4def-940b-0421030a5b68',
		'IdentityProvider.ReadWrite.All': '90db2b9a-d928-4d33-a4dd-8442ae3d41e4',
		'IdentityProvider.Read.All': 'e321f0bb-e7f7-481e-bb28-e3b0b32d4bd0',
		'AdministrativeUnit.ReadWrite.All': '5eb59dd3-1da2-4329-8733-9dabdc435916',
		'AdministrativeUnit.Read.All': '134fd756-38ce-4afd-ba33-e9623dbe66c2',
		'InformationProtectionPolicy.Read.All': '19da66cb-0fb0-4390-b071-ebc76a349482',
		'Notes.Read.All': '3aeca27b-ee3a-4c2b-8ded-80376e2134a4',
		'User.Invite.All': '09850681-111b-4a89-9bed-3f2cae46d706',
		'Files.ReadWrite.All': '75359482-378d-4052-8f01-80520e7db3cd',
		'ThreatIndicators.ReadWrite.OwnedBy': '21792b6c-c986-4ffc-85de-df9da54b52fa',
		'SecurityActions.ReadWrite.All': 'f2bf083f-0179-402a-bedb-b2784de8a49b',
		'SecurityActions.Read.All': '5e0edab9-c148-49d0-b423-ac253e121825',
		'SecurityEvents.ReadWrite.All': 'd903a879-88e0-4c09-b0c9-82f6a1333f84',
		'SecurityEvents.Read.All': 'bf394140-e372-4bf9-a898-299cfc7564e5',
		'Chat.ReadWrite.All': '294ce7c9-31ba-490a-ad7d-97a7d075e4ed',
		'IdentityRiskEvent.ReadWrite.All': 'db06fb33-1953-4b7b-a2ac-f1e2c854f7ae',
		'IdentityRiskyUser.ReadWrite.All': '656f6061-f9fe-4807-9708-6a2e0934df76',
		'Files.Read.All': '01d4889c-1287-42c6-ac1f-5d1e02578ef6',
		'IdentityRiskEvent.Read.All': '6e472fd1-ad78-48da-a0f0-97ab2c6b769e',
		'EduRoster.ReadBasic.All': '0d412a8c-a06c-439f-b3ec-8abcf54d2f96',
		'EduRoster.Read.All': 'e0ac9e1b-cb65-4fc5-87c5-1a8bc181f648',
		'EduRoster.ReadWrite.All': 'd1808e82-ce13-47af-ae0d-f9b254e6d58a',
		'EduAssignments.ReadBasic.All': '6e0a958b-b7fc-4348-b7c4-a6ab9fd3dd0e',
		'EduAssignments.ReadWriteBasic.All': 'f431cc63-a2de-48c4-8054-a34bc093af84',
		'EduAssignments.Read.All': '4c37e1b6-35a1-43bf-926a-6f30f2cdf585',
		'EduAssignments.ReadWrite.All': '0d22204b-6cad-4dd0-8362-3e3f2ae699d9',
		'EduAdministration.Read.All': '7c9db06a-ec2d-4e7b-a592-5a1e30992566',
		'EduAdministration.ReadWrite.All': '9bc431c3-b8bc-4a8d-a219-40f10f92eff6',
		'IdentityRiskyUser.Read.All': 'dc5007c0-2d7d-4c42-879c-2dab87571379',
		'User.ReadWrite.All': '741f803b-c850-494e-b5df-cde7c675a1ca',
		'User.Read.All': 'df021288-bdef-4463-88db-98f22de89214',
		'AuditLog.Read.All': 'b0afded3-3588-46d8-8b3d-9842eff778da',
		'Application.ReadWrite.OwnedBy': '18a4783c-866b-4cc7-a460-3d5e5662c884',
		'User.Export.All': '405a51b5-8d8d-430b-9842-8be4b0e9f324',
		'ProgramControl.ReadWrite.All': '60a901ed-09f7-4aa5-a16e-7dd3d6f9de36',
		'ProgramControl.Read.All': 'eedb7fdd-7539-4345-a38b-4839e4a84cbd',
		'AccessReview.ReadWrite.All': 'ef5f7d5c-338f-44b0-86c3-351f46c8bb5f',
		'AccessReview.Read.All': 'd07a8cc0-3d51-4b77-b3b0-32704d1f69fa',
		'Reports.Read.All': '230c1aed-a721-4c5d-9cb4-a90514e508ef',
		'People.Read.All': 'b528084d-ad10-4598-8b93-929746b4d7d6',
		'Chat.UpdatePolicyViolation.All': '7e847308-e030-4183-9899-5235d7270f58',
		'Chat.Read.All': '6b7d71aa-70aa-4810-a8d9-5d9fb2830017',
		'ChannelMessage.Read.All': '7b2449af-6ccd-4f4d-9f78-e550c193f0d1',
		'ChannelMessage.UpdatePolicyViolation.All': '4d02b0cc-d90b-441f-8d82-4fb55c34d6bb',
		'Application.ReadWrite.All': '1bfefb4e-e0b5-418b-a88f-73c46d2cc8e9',
		'MailboxSettings.ReadWrite': '6931bccd-447a-43d1-b442-00a195474933',
		'Domain.ReadWrite.All': '7e05723c-0bb0-42da-be95-ae9f08a6e53c',
		'MailboxSettings.Read': '40f97065-369a-49f4-947c-6a255697ae91',
		'Mail.Read': '810c84a8-4a9e-49e6-bf7d-12d183f40d01',
		'Mail.ReadWrite': 'e2a3a72e-5f79-4c64-b1b1-878b674786c9',
		'Mail.Send': 'b633e1c5-b582-4048-a93e-9f11b44c7e96',
		'Contacts.Read': '089fe4d0-434a-44c5-8827-41ba8a0b17f5',
		'Contacts.ReadWrite': '6918b873-d17a-4dc1-b314-35f528134491',
		'Directory.Read.All': '7ab1d382-f21e-4acd-a863-ba3e13f7da61',
		'Directory.ReadWrite.All': '19dbc75e-c2e2-444c-a770-ec69d8559fc7',
		'Device.ReadWrite.All': '1138cb37-bd11-4084-a2b7-9f71582aeddb',
		'Calendars.Read': '798ee544-9d2d-430c-a058-570e29e34338',
		'Calendars.ReadWrite': 'ef54d2bf-783f-4e0f-bca1-3210c0444d99',
		'IdentityUserFlow.Read.All': '1b0c317f-dd31-4305-9932-259a8b6e8099',
		'IdentityUserFlow.ReadWrite.All': '65319a09-a2be-469d-8782-f6b07debf789',
		'OnlineMeetings.ReadWrite.All': 'b8bb2037-6e08-44ac-a4ea-4674e010e2a4',
		'OnlineMeetings.Read.All': 'c1684f21-1984-47fa-9d61-2dc8c296bb70',
		'Calls.AccessMedia.All': 'a7a681dc-756e-4909-b988-f160edc6655f',
		'Calls.JoinGroupCallAsGuest.All': 'fd7ccf6b-3d28-418b-9701-cd10f5cd2fd4',
		'Calls.JoinGroupCall.All': 'f6b49018-60ab-4f81-83bd-22caeabfed2d',
		'Calls.InitiateGroupCall.All': '4c277553-8a09-487b-8023-29ee378d8324',
		'Calls.Initiate.All': '284383ee-7f6e-4e40-a2a8-e85dcb029101',
		'OrgContact.Read.All': 'e1a88a34-94c4-4418-be12-c87b00e26bea',
		'DeviceManagementApps.ReadWrite.All': '78145de6-330d-4800-a6ce-494ff2d33d07',
		'DeviceManagementConfiguration.ReadWrite.All': '9241abd9-d0e6-425a-bd4f-47ba86e767a4',
		'DeviceManagementManagedDevices.PrivilegedOperations.All': '5b07b0dd-2377-4e44-a38d-703f09a0dc3c',
		'DeviceManagementManagedDevices.ReadWrite.All': '243333ab-4d21-40cb-a475-36241daa0842',
		'DeviceManagementRBAC.ReadWrite.All': 'e330c4f0-4170-414e-a55a-2f022ec2b57b',
		'DeviceManagementServiceConfig.ReadWrite.All': '5ac13192-7ace-4fcf-b828-1a26f28068ee',
		'AppRoleAssignment.ReadWrite.All': '06b708a9-e830-4db3-a914-8e69da51d44f',
		'DelegatedPermissionGrant.ReadWrite.All': '8e8e4742-1d95-4f68-9d56-6ee75648c72a',
		'TeamsActivity.Read.All': '70dec828-f620-4914-aa83-a29117306807',
		'PrivilegedAccess.Read.AzureAD': '4cdc2547-9148-4295-8d11-be0db1391d6b',
		'PrivilegedAccess.Read.AzureADGroup': '01e37dc9-c035-40bd-b438-b2879c4870a6',
		'PrivilegedAccess.Read.AzureResources': '5df6fe86-1be0-44eb-b916-7bd443a71236',
		'PrivilegedAccess.ReadWrite.AzureAD': '854d9ab1-6657-4ec8-be45-823027bcd009',
		'PrivilegedAccess.ReadWrite.AzureADGroup': '2f6817f8-7b12-4f0f-bc18-eeaf60705a9e',
		'PrivilegedAccess.ReadWrite.AzureResources': '6f9d5abc-2db6-400b-a267-7de22a40fb87',
		'ThreatIndicators.Read.All': '197ee4e9-b993-4066-898f-d6aecc55125b',
		'UserNotification.ReadWrite.CreatedByApp': '4e774092-a092-48d1-90bd-baad67c7eb47',
		'Application.Read.All': '9a5d68dd-52b0-4cc2-bd40-abcf44ac3a30',
		'BitlockerKey.Read.All': '57f1cf28-c0c4-4ec3-9a30-19a2eaaf2f6e',
		'BitlockerKey.ReadBasic.All': 'f690d423-6b29-4d04-98c6-694c42282419',
		'GroupMember.Read.All': '98830695-27a2-44f7-8c18-0c3ebc9698f6',
		'GroupMember.ReadWrite.All': 'dbaae8cf-10b5-4b86-a4a1-f871c94c6695',
		'Group.Create': 'bf7b1a76-6e77-406b-b258-bf5c7720e98f',
		'ThreatAssessment.Read.All': 'f8f035bb-2cce-47fb-8bf5-7baf3ecbee48',
		'Schedule.Read.All': '7b2ebf90-d836-437f-b90d-7b62722c4456',
		'Schedule.ReadWrite.All': 'b7760610-0545-4e8a-9ec3-cce9e63db01c',
		'CallRecords.Read.All': '45bbb07e-7321-4fd7-a8f6-3ff27e6a81c8',
		'Policy.ReadWrite.ConditionalAccess': '01c0a623-fc9b-48e9-b794-0756f8e8f067',
		'UserAuthenticationMethod.ReadWrite.All': '50483e42-d915-4231-9639-7fdb7fd190e5',
		'UserAuthenticationMethod.Read.All': '38d9df27-64da-44fd-b7c5-a6fbac20248f',
		'TeamsTab.Create': '49981c42-fd7b-4530-be03-e77b21aed25e',
		'TeamsTab.Read.All': '46890524-499a-4bb2-ad64-1476b4f3e1cf',
		'TeamsTab.ReadWrite.All': 'a96d855f-016b-47d7-b51c-1218a98d791c',
		'Domain.Read.All': 'dbb9058a-0e50-45d7-ae91-66909b5d4664',
		'Policy.ReadWrite.ApplicationConfiguration': 'be74164b-cff1-491c-8741-e671cb536e13',
		'Device.Read.All': '7438b122-aefc-4978-80ed-43db9fcc7715',
		'User.ManageIdentities.All': 'c529cfca-c91b-489c-af2b-d92990b66ce6',
		'UserShiftPreferences.Read.All': 'de023814-96df-4f53-9376-1e2891ef5a18',
		'UserShiftPreferences.ReadWrite.All': 'd1eec298-80f3-49b0-9efb-d90e224798ac',
		'Notes.ReadWrite.All': '0c458cef-11f3-48c2-a568-c66751c238c0',
		'Sites.FullControl.All': 'a82116e5-55eb-4c41-a434-62fe8a61c773',
		'Sites.Manage.All': '0c0bf378-bf22-4481-8f81-9e89a9b4960a',
		'EntitlementManagement.Read.All': 'c74fd47d-ed3c-45c3-9a9e-b8676de685d2',
		'EntitlementManagement.ReadWrite.All': '9acd699f-1e81-4958-b001-93b1d2506e19',
		'Channel.Create': 'f3a65bd4-b703-46df-8f7e-0174fea562aa',
		'Channel.Delete.All': '6a118a39-1227-45d4-af0c-ea7b40d210bc',
		'ChannelSettings.Read.All': 'c97b873f-f59f-49aa-8a0e-52b32d762124',
		'ChannelSettings.ReadWrite.All': '243cded2-bd16-4fd6-a953-ff8177894c3d',
		'Team.ReadBasic.All': '2280dda6-0bfd-44ee-a2f4-cb867cfc4c1e',
		'Channel.ReadBasic.All': '59a6b24b-4225-4393-8165-ebaec5f55d7a',
		'TeamSettings.ReadWrite.All': 'bdd80a03-d9bc-451d-b7c4-ce7c63fe3c8f',
		'TeamSettings.Read.All': '242607bd-1d2c-432c-82eb-bdb27baa23ab',
		'TeamMember.Read.All': '660b7406-55f1-41ca-a0ed-0b035e182f3e',
		'TeamMember.ReadWrite.All': '0121dc95-1b9f-4aed-8bac-58c5ac466691',
		'ChannelMember.Read.All': '3b55498e-47ec-484f-8136-9013221c06a9',
		'ChannelMember.ReadWrite.All': '35930dcf-aceb-4bd1-b99a-8ffed403c974',
		'Policy.ReadWrite.AuthenticationFlows': '25f85f3c-f66c-4205-8cd5-de92dd7f0cec',
		'Policy.ReadWrite.AuthenticationMethod': '29c18626-4985-4dcd-85c0-193eef327366',
		'Policy.ReadWrite.Authorization': 'fb221be6-99f2-473f-bd32-01c6a0e9ca3b',
		'Chat.ReadBasic.All': 'b2e060da-3baf-4687-9611-f4ebc0f0cbde',
		'Policy.Read.PermissionGrant': '9e640839-a198-48fb-8b9a-013fd6f6cbcd',
		'Policy.ReadWrite.PermissionGrant': 'a402ca1c-2696-4531-972d-6e5ee4aa11ea',
		'Printer.Read.All': '9709bb33-4549-49d4-8ed9-a8f65e45bb0f',
		'Printer.ReadWrite.All': 'f5b3f73d-6247-44df-a74c-866173fddab0',
		'PrintJob.Manage.All': '58a52f47-9e36-4b17-9ebe-ce4ef7f3e6c8',
		'PrintJob.Read.All': 'ac6f956c-edea-44e4-bd06-64b1b4b9aec9',
		'PrintJob.ReadBasic.All': 'fbf67eee-e074-4ef7-b965-ab5ce1c1f689',
		'PrintJob.ReadWrite.All': '5114b07b-2898-4de7-a541-53b0004e2e13',
		'PrintJob.ReadWriteBasic.All': '57878358-37f4-4d3a-8c20-4816e0d457b1',
		'PrintTaskDefinition.ReadWrite.All': '456b71a7-0ee0-4588-9842-c123fcc8f664',
		'Teamwork.Migrate.All': 'dfb0dd15-61de-45b2-be36-d6a69fba3c79',
		'TeamsAppInstallation.ReadForChat.All': 'cc7e7635-2586-41d6-adaa-a8d3bcad5ee5',
		'TeamsAppInstallation.ReadForTeam.All': '1f615aea-6bf9-4b05-84bd-46388e138537',
		'TeamsAppInstallation.ReadForUser.All': '9ce09611-f4f7-4abd-a629-a05450422a97',
		'TeamsAppInstallation.ReadWriteForChat.All': '9e19bae1-2623-4c4f-ab6e-2664615ff9a0',
		'TeamsAppInstallation.ReadWriteForTeam.All': '5dad17ba-f6cc-4954-a5a2-a0dcc95154f0',
		'TeamsAppInstallation.ReadWriteForUser.All': '74ef0291-ca83-4d02-8c7e-d2391e6a444f',
		'TeamsAppInstallation.ReadWriteSelfForChat.All': '73a45059-f39c-4baf-9182-4954ac0e55cf',
		'TeamsAppInstallation.ReadWriteSelfForTeam.All': '9f67436c-5415-4e7f-8ac1-3014a7132630',
		'TeamsAppInstallation.ReadWriteSelfForUser.All': '908de74d-f8b2-4d6b-a9ed-2a17b3b78179',
		'Team.Create': '23fc2474-f741-46ce-8465-674744c5c361',
		'TeamMember.ReadWriteNonOwnerRole.All': '4437522e-9a86-4a41-a7da-e380edd4a97d',
		'TermStore.Read.All': 'ea047cc2-df29-4f3e-83a3-205de61501ca',
		'TermStore.ReadWrite.All': 'f12eb8d6-28e3-46e6-b2c0-b7e4dc69fc95',
		'ServiceHealth.Read.All': '79c261e0-fe76-4144-aad5-bdc68fbe4037',
		'ServiceMessage.Read.All': '1b620472-6534-4fe6-9df2-4680e8aa28ec',
		'ShortNotes.Read.All': '0c7d31ec-31ca-4f58-b6ec-9950b6b0de69',
		'ShortNotes.ReadWrite.All': '842c284c-763d-4a97-838d-79787d129bab',
		'Policy.Read.ConditionalAccess': '37730810-e9ba-4e46-b07e-8ca78d182097',
		'RoleManagement.Read.All': 'c7fbd983-d9aa-4fa7-84b8-17382c103bc4',
		'CallRecord-PstnCalls.Read.All': 'a2611786-80b3-417e-adaa-707d4261a5f0',
		'ChatMessage.Read.All': 'b9bb2381-47a4-46cd-aafb-00cb12f68504',
		'TeamsTab.ReadWriteForChat.All': 'fd9ce730-a250-40dc-bd44-8dc8d20f39ea',
		'TeamsTab.ReadWriteForTeam.All': '6163d4f4-fbf8-43da-a7b4-060fe85ed148',
		'TeamsTab.ReadWriteForUser.All': '425b4b59-d5af-45c8-832f-bb0b7402348a',
		'APIConnectors.Read.All': 'b86848a7-d5b1-41eb-a9b4-54a4e6306e97',
		'APIConnectors.ReadWrite.All': '1dfe531a-24a6-4f1b-80f4-7a0dc5a0a171',
		'ChatMember.Read.All': 'a3410be2-8e48-4f32-8454-c29a7465209d',
		'ChatMember.ReadWrite.All': '57257249-34ce-4810-a8a2-a03adf0c5693',
		'Chat.Create': 'd9c48af6-9ad9-47ad-82c3-63757137b9af',
		'PrintSettings.Read.All': 'b5991872-94cf-4652-9765-29535087c6d8',
		'SharePointTenantSettings.ReadWrite.All': '19b94e34-907c-4f43-bde9-38b1909ed408',
		'EventListener.Read.All': 'b7f6385c-6ce6-4639-a480-e23c42ed9784',
		'EventListener.ReadWrite.All': '0edf5e9e-4ce8-468a-8432-d08631d18c43',
		'CustomAuthenticationExtension.Read.All': '88bb2658-5d9e-454f-aacd-a3933e079526',
		'Tasks.Read.All': 'f10e1f91-74ed-437f-a6fd-d6ae88e26c1f',
		'CrossTenantInformation.ReadBasic.All': 'cac88765-0581-4025-9725-5ebc13f729ee',
		'CrossTenantUserProfileSharing.ReadWrite.All': '306785c5-c09b-4ba0-a4ee-023f3da165cb',
		'AuthenticationContext.ReadWrite.All': 'a88eef72-fed0-4bf7-a2a9-f19df33f8b83',
		'ThreatSubmission.Read.All': '86632667-cd15-4845-ad89-48a88e8412e1',
		'InformationProtectionContent.Sign.All': 'cbe6c7e4-09aa-4b8d-b3c3-2dbb59af4b54',
		'ThreatSubmissionPolicy.ReadWrite.All': '926a6798-b100-4a20-a22f-a4918f13951d',
		'DirectoryRecommendations.ReadWrite.All': '0e9eea12-4f01-45f6-9b8d-3ea4c8144158',
		'OnlineMeetingRecording.Read.All': 'a4a08342-c95d-476b-b943-97e100569c8d',
		'LicenseAssignment.ReadWrite.All': '5facf0c1-8979-4e95-abcf-ff3d079771c0',
		'DirectoryRecommendations.Read.All': 'ae73097b-cb2a-4447-b064-5d80f6093921',
		'CrossTenantUserProfileSharing.Read.All': '8b919d44-6192-4f3d-8a3b-f86f8069ae3c',
		'Directory.Write.Restricted': 'f20584af-9290-4153-9280-ff8bb2c0ea7f',
		'OnlineMeetingTranscript.Read.All': 'a4a80d8d-d283-4bd8-8504-555ec3870630',
		'SharePointTenantSettings.Read.All': '83d4163d-a2d8-4d3b-9695-4ae3ca98f888',
		'CustomAuthenticationExtension.ReadWrite.All': 'c2667967-7050-4e7e-b059-4cbbb3811d03',
		'InformationProtectionContent.Write.All': '287bd98c-e865-4e8c-bade-1a85523195b9',
		'Tasks.ReadWrite.All': '44e666d1-d276-445b-a5fc-8815eeb81d55',
		'AuthenticationContext.Read.All': '381f742f-e1f8-4309-b4ab-e3d91ae4c5c1',
	}
	app_rol_id_to_name = dict([(x[1], x[0]) for x in name_to_app_rol_id.items()])


permissions_needed_name = ["Directory.ReadWrite.All", "Group.ReadWrite.All", "User.ReadWrite.All", "TeamMember.ReadWrite.All"]

resourceAccess = [{"id": ApplicationPermissions.name_to_app_rol_id[name], "type": "Role"} for name in permissions_needed_name]


class Manifest(object):

	def __init__(self, fd, adconnection_alias, adconnection_id, domain, logger=None):
		# type: ("SupportsRead", str, str, str, "logging.Logger") -> None
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
				"resourceAccess": resourceAccess
		}

		for access in self.manifest['requiredResourceAccess']:
			if permissions["resourceAppId"] == access['resourceAppId']:
				# append permissions without duplicates
				[access["resourceAccess"].append(p) for p in permissions["resourceAccess"] if p not in access["resourceAccess"]]
				break
		else:
			self.manifest['requiredResourceAccess'].append(permissions)

