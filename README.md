# Microsoft 365 connector

This package provides functionality to synchronize UCS user and group accounts
to Azure AD to provision Microsoft 365 accounts for them.
The accounts can be configured for synchronization to multiple Azure AD domains.

This package contains a UMC wizard, extended attributes and hooks for user and
group accounts and listener modules to do the actual synchronization.

The package is the basis for the Office365 App available in the UCS App Center,
which can only be installed on UCS Systems with role Master or Backup.

* Credentials: https://hutten.knut.univention.de/dokuwiki/externe_konten:office365
* Web-Interfaces: https://portal.azure.com/
* Web-Interfaces Teams: admin.teams.microsoft.com (for Teams)

# User Story

* After installation of this App UCS user accounts have a new Tab "Microsoft 365"
  in UMC, which offers a checkbox to Enable the Synchronization of the account
  to an Azure Active Directory. Below that checkbox, the "alias" name of a
  target Azure AD can be selected. If none is selected, then a default
  specified via UCR variable "office365/defaultalias" will be selected.
* Before synchronization can start to work, an App-specific wizard needs to be
  run to configure ("initialize") the Azure AD Connection.
  The UCR variable "office365/adconnection/wizard" specifies the alias name
  of the Azure AD Connection that it will configure.
* AD Connections are represented as UDM "office365/ad-connection" objects and
  also visible in UCR below office365/adconnection/alias/.
* Multi-Connection support has been added in App-Version 3.0. Migration from
  earlier App-Versions is automatic but can optionally be disabled via the UCR
  variable "office365/migrate/adconnectionalias". The automatic migration
  migrates the existing initialized AD Connection to "defaultADconnection",
  by creating an udm object of type "office365/ad-connection" and setting the
  UCR variable: "office365/adconnection/alias/defaultADconnection".
  Optionally the migration can be started manually at a later stage by running
  the command
  /usr/share/univention-office365/scripts/migrate_to_adconnectionalias
* Group Synchronization doesn't happen by default. The UCR variable
  "office365/groups/sync" needs to activated for this. After changing that
  UCR variable the Univention Directory Listener Needs to be restarted.
  Group synchronization may put some load on the server, because the selection
  of which groups to synchronize happens automatically, by checking nested group
  memberships of user accounts that are enabled for synchronization.
* In LDAP, enabled user accounts are marked by the attribute
  "univentionOffice365Enabled". The target Azure ADs can be seen in the
  multivalue LDAP attribute "univentionOffice365ADConnectionAlias".
  After successful synchronization, the Listener modules store the
  Azure AD object IDs at the corresponding UCS user and group objects.
  These object IDs are specific for each target Azure AD instance.
  This information is used for internal book-keeping and not easily accessible
  via LDAP search, because it is stored encoded as base64(zipped(json(dict)))
  in an LDAP attribute "univentionOffice365Data". For user objects this
  encoded dictionary additionally includes the Azure AD specific userPrincipalNames,
  which are visible in the UMC users/user tab "Microsoft 365". Their presence
  in the UMC provides the possibility to quickly check, if the initial
  synchronization of an account has been successful.
* The connector is able to configure O365 subscriptions at user objects. Subscriptions are
  only assigned when a user is enabled for Azure synchronisation, re-enabling a user also
  configures subscriptions. By default, it is tried to enable a subscription with the
  following Azure-internal identifiers:
  'SHAREPOINTWAC, SHAREPOINTWAC_DEVELOPER, OFFICESUBSCRIPTION'.
  The default can be overruled by UCR office365/subscriptions/service_plan_names. To see
  available subscriptions use the tool print_subscriptions.
  Fine-grained subscription policies can be set with UDM objects of the type
  office365/profile. Here, a subscription name and individually white or blacklisted
  service plans can be configured. These profiles can be set at udm groups/group objects.
  When a member of such a group is enabled for synchronisation, the user listener will
  search for the first group where an office365/profile is set, and configure the azure
  user object accordingly.
* It is possible to use external Office clients with the Connector, like mobile apps
  or Office Desktop products. A respective subscription / service plan is required in Azure.
  These external programs need their activation tokens reset in a 90-day period, or will
  require frequent (multiple per hour) logins with Azure credentials to continue working.
  A cronjob exists which calls o365_usertokens, to reset these tokens in a configurable
  interval. After the tokens for a user are reset, the user has to re-authenticate once.
* The connector never syncs the user password (hash). A SAML service provider is configured
  to handle login against the UCS SAML Identity Provider. When configuring multiple AD
  connections, additional SAML SPs have to be configured as per documentation. To
  configure the SAML connection, the wizard offers a powershell script that has to be
  executed on an MS Windows OS.

# Product Tests

* App Installation and Update via Test App Center
* Setup an Azure AD Connection via the UMC wizard, Setup SAML with instructions provided
  by the wizard. While using the wizard: Verify that the provided Screenshots represent
  the current presentation in the Azure Portal (the webinterface changes quite often).
* Activate the group listener via UCR + listener restart. Enable some users
  and check that they and their groups have been synced (most of that is covered by
  ucs-tests).
* Check the SAML login and logout via Browser, and, if available, desktop/mobile
  Office App. Check SAML login service provider initiated
  (starting at login.microsoftonline.com) and IdP initiated by the UCS Portal tile.
* If desktop/mobile App is available. Test that re-authentication is required after
  executing the token reset script o365_usertokens for a user. Otherwise, check
  the Azure user object with o365_list_users for the last token reset date
* Create a second AD connection via manage_adconnections, run the setup wizard for
  the new domain, setup a second SAML IdP according to the manual. Test SSO for an
  account that is synced to both ADs.


# Automated tests exist for

* API connection
* user creation, modification and removal
* UCR attribute settings (sync, anonymize, never sync)
* Lock and unlock user
* Handling of a user in multiple AD connections
* Group synchronisation

# Documentation

* http://docs.software-univention.de/manual-4.4.html#idmcloud:o365

# Tools

* /usr/share/univention-office365/scripts/manage_adconnections list
* /usr/share/univention-office365/scripts/print_users_and_groups
* /usr/share/univention-office365/scripts/print_subscriptions
* /usr/share/univention-office365/scripts/o365_list_users
* /usr/share/univention-office365/scripts/o365_usertokens

# Design

Azure is Microsofts cloud service. It has a so called Active Directory (Azure AD) component, that can manage Users, Groups, Applications, Roles, Permissions etc. We need it to manage users, groups, logins and Office365 licences.

To synchronize an on-premises AD with Azure AD, "Azure AD Connect" can be used (https://azure.microsoft.com/en-us/documentation/articles/active-directory-aadconnect/). There is also a big C# library for communication for MS Azure. Since this non of this is not an option, we'll use the Azure Graph API.

The API is a moving target, but has stable versions that can be used explicitly. We're currently using Version 1.6 of the REST API (see https://msdn.microsoft.com/en-us/Library/Azure/Ad/Graph/api/api-catalog). Other protocols (WS, XML) exist.

Prior to communication with the Azure API, authentication and authorization is done through OAuth2.

After installing the App, a wizard (similar to UCS@school and UCC) will run that will request the UCS user to make some configuration on its behalf. Mainly that is registering and configuring an application in Azure AD. Some of this can be supported pragmatically, some can't...

The wizard must retrieve the following data from the user:
* the client ID
* the Federation Data Document Url
* the Azure Application manifest

The manifest is downloaded by the user from their Azure application. The manifest contains, among other things, permissions for the application.
The function *def transform* in azure_auth.py appends needed permissions to the manifest, which is then reuploaded by the user.
This includes permissions for the Azure Active Directory Graph API (resourceAppId: 00000002-0000-0000-c000-000000000000)
and the Microsoft Graph API (resourceAppId: 00000003-0000-0000-c000-000000000000). The permissions will be displayed in the *API permissions* Tab in the Azure Portal.

The added Azure Active Directory Graph API permissions are:
Permission Name: Directory.ReadWrite.All, Type: Application
{"id": "78c8a3c8-a07e-4b9e-af1b-b5ccab50a175", "type": "Role"}]},
The added Microsoft Graph permissions are:
# Permission Name: Directory.ReadWrite.All, Type: Application
{"id": "19dbc75e-c2e2-444c-a770-ec69d8559fc7", "type": "Role"},
# Permission Name: Group.ReadWrite.All, Type: Application
{"id": "62a82d76-70ea-41e2-9197-370581804d09", "type": "Role"},
# Permission Name: User.ReadWrite.All, Type: Application
{"id": "741f803b-c850-494e-b5df-cde7c675a1ca", "type": "Role"},
# Permission Name: TeamMember.ReadWrite.All, Type: Application
{"id": "0121dc95-1b9f-4aed-8bac-58c5ac466691", "type": "Role"}]}}


## Authorization Code Grant Flow - ***not** used by listener!*

With this data the OAuth dance can begin. See "Authorization Code Grant Flow" (see https://msdn.microsoft.com/en-us/library/azure/dn645542.aspx).

In short:
* redirect the user to authenticate at an Azure-login
* user authorizes the requested permissions for the UCS App
* user gets redirected from Azure to the configured callback-URI (https://DC.DOM/office365/mycallback)
* the callback extracts a token from the URL and uses it to get some other tokens
* those tokens can be used to access the Azure AD and to refresh themselfs when they expire (3600s)
* when the refresh token has expired the dance begins from the start. Currently it is unknown how long it lasts... at least 6h it seams... The Azure doc states: "Refresh tokens do not have specified lifetimes. Typically, the lifetimes of refresh tokens are relatively long. [..] The client application needs to expect and handle errors..." (see https://msdn.microsoft.com/en-us/library/azure/dn645536.aspx)

We dance with a partner: requests-oauthlib (https://github.com/requests/requests-oauthlib). It does well, except for the refresh handling. This should be fixed in their code. But handling it ourselves is not a problem. Requests-oauthlib uses the "requests" lib for handling the HTTP requests. The requests lib might one day end up in the Python standard library.

## Client credentials flow - *used by listener*

With the help of the UMC wizard a SSL certificate is uploaded to Azure. The secret key is used by us to sign our requests and to verify their tokens. No user interaction is required to fetch new tokens.

The downside of the client credentials flow is, that some operations on the AAD are excluded from application permissions. Most notable an application does not hae the rights to reset user passwords or to delete entities (including users or groups) (see https://msdn.microsoft.com/Library/Azure/Ad/Graph/howto/azure-ad-graph-api-permission-scopes#DirectoryRWDetail).

Now that we can authenticate, we can synchronize the selected users and groups with the Azure directory and manage the users licenses. "Synchronization" will be one-way: only from UCS to Azure AD. It should include the users minimal contact data and the groups that the users are in. It is possible to configure through UCRVs which attributes are synchronized and which not. It can also be configured if attributes should be anonymized.


# Dependencies / Constraints

## Teams
In order to create Teams, at least one group owner must be set.
To convert a group into a team, the group must be of type MS365, not security group. The doc says so, but the API allows creating of a team from a security group
To create a team, all group owners must have a license that includes Teams.

# Implementation

## Implementation State

Currently, there is

* a commandline simulation for the listener module, usage: consoletest.py
* a WSGI script simulating the UMC wizard: wizard/umc_wizard.py
* a callback (also WSGI script) for the OAuth interaction: wizard/azure_callback.py
* a logging class to use the Python logging class automagically together with syslog and univention.debug (untested) depending on system it runs on --> will be removed, all logging will go to univention.debug, LISTENER facility.

## Classes

```
|-  UDM obj only   -|-  UDM <-> AAD obj  -|- AAD obj only -|

office365-user.py  --\
                     +--> listener.py --> azure_handler.py ---(HTTP)--> AzureAD
office365-group.py --/                         |                          |
                                               |                          |
                                               v                          |
                                           azure_auth.py -----(HTTP)--> OAuth2
                                               ^                          |
                                               |                          |
                                         azure_callback.py <--(HTTP)------+
```

listener.py, azure_handler.py and azure_auth.py are written so that they can be used outside the listener code.
When modifying code, please keep the separation of where which objects are used.

## Async daemon

Some azure calls need a try-sleep-retry (graph.create_group, retry(graph.add_group_owner), retry(graph.create_team_from_group)). To not block the listener at this point we have a async daemon for special azure calls *univention-ms-office-async* (share/univention-ms-office-async).

Started via *univention-ms-office-async.service* this daemon checks */var/lib/univention-office365/async* for json files with following format:
```
{
  "function_name": "convert_from_group_to_team",
  "ad_connection_alias": "alias1",
  "api_version": 1,
  "parameters": {
     "param1": "value1",
     "param2": "value2",
  }
}
```
If the file can be verified (e.g. function exists or ad_connection_alias is available) *function_name* with the kwarg parameters *parameters* is executed on the connection *ad_connection_alias*. If the job can't be verified or is successful the job is removed.

The daemon is just:
* drop privileges to listener(nogroup)
* while loop
* find jobs in */var/lib/univention-office365/async*
* verify job -> success: execute job, failed: remove job
* execute job -> success: remove file, failed: go to next job (move failed jobs after *retry-count* times to */var/lib/univention-office365/async/failed*)
* wait(30)

Logfile: /var/log/univention/listener_modules/ms-office-async.log.log
Autostart: univention-ms-office-async/autostart
Job dir: /var/lib/univention-office365/async (make sure owned by listener)
Failed dir: /var/lib/univention-office365/async/failed (make sure owned by listener)

## Async calls

```
from univention.office365.api_helper import write_async_job
write_async_job(a_function_name='modify_group', a_ad_connection_alias='o365domain', object_id="params", new_name="aaaa", ...)
```

# Test coverage

* Test cases for ucs-test: 92_office365/*
* Jenkins Job UCS-4.4-2>Product Tests>product-test-component-office365

# Manual Installation (Legacy Warning: UCS 4.1)

* install ucs-4.1/component/univention-office365
* to write debug messages at error level set office365/debug/werror=yes and restart listener
* go to https://FQDN/univention-office365/wizard
* register app in Azure
* go to https://FQDN/univention-office365/wizard?client_id=<........-....-....-....-............>
* Authorize
* Enable UDM property UniventionOffice365Enabled for users/groups
* observe listener.log

# TODO

* update this document
