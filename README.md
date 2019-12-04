# Office 365 connector

This package provides functionality to synchronize UCS user and group accounts
to Azure AD to provision MS Office 365 accounts for them.
The accounts can be configured for synchonization to multiple Azure AD domains.

This package contains a UMC wizard, extended attributes and hooks for user and
group accounts and listener modules to do the actual synchronization.

The package is the basis for the Office365 App available in the UCS App Center,
which can only be installed on UCS Systems with role Master or Backup.

# User Story

* After installation of this App UCS user accounts have a new Tab "Office 365"
  in UMC, which offers a checkbox to Enable the Syncronization of the account
  to an Azure Active Directory. Below that checkbox, the "alias" name of a
  target Azure AD can be selected. If none is selected, then a default
  specified via UCR variable "office365/defaultalias" will be selected.
* Before syncronization can start to work, an App-specific wizard needs to be
  run to configure ("initialize") the Azure AD Connection.
  The UCR variable "office365/adconnection/wizard" specifies the alias name
  of the Azure AD Connection that it will configure.
* AD Connections are represented as UDM "office365/ad-connection" objects and
  also visible in UCR as office365/adconnection/alias/*.
* Multi-Connection support has been added in App-Version 4.0. Migration from
  earlier App-Versions is automatic but can optionally be disabled via the UCR
  variable "office365/migrate/adconnectionalias". The automatic migration
  migrates the existing initialized AD Connection to "defaultADconnection",
  by creating an udm object of type "office365/ad-connection" and setting the
  UCR variable: "office365/adconnection/alias/defaultADconnection".
  Optionally the migration can be started manually at a later stange by running
  the command
  /usr/share/univention-office365/scripts/migrate_to_adconnectionalias
* Group Synchonization doesn't happen by default. The UCR variable
  "office365/groups/sync" needs to activated for this. After changing that
  UCR variable the Univention Directory Listener Needs to be restarted.
  Group synchronization may put some load on the server, because the selection
  of which goups to synchronize happens automatically, by checking nested group
  memberships of user accounts that are enabled for synchronization.
* In LDAP, enabled user accounts are marked by and attribute
  "univentionOffice365Enabled". The target Azure ADs can be seen in the
  multialue LDAP attribute "univentionOffice365ADConnectionAlias".
  After successfull synchronization, the Listener modules store the
  Azure AD object IDs at the corresponding UCS user and group objects.
  These object IDs are specific for each target Azure AD instance.
  This information is used for internal book-keeping and not easily accessible
  via LDAP search, because it is stored as encoded as base64(zipped(json(dict)))
  in an LDAP attribute "univentionOffice365Data". For user objects this
  encoded dictionary additionally includes the Azure AD specific userPrincipalNames,
  which are visible in the UMC users/user tab "Office 365". Their presence
  in the UMC provides a possiblity to quickly check, if the initial
  synchronization of an account has been successful.

# Documentation

* http://docs.software-univention.de/manual-4.4.html#idmcloud:o365

# Tools

* /usr/share/univention-office365/scripts/manage_adconnections list

# Design

Azure is Microsofts cloud service. It has a so called Active Directory (Azure AD) component, that can manage Users, Groups, Applications, Roles, Permissions etc. We need it to manage users, groups, logins and Office365 licences.

To synchronize an on-premises AD with Azure AD, "Azure AD Connect" can be used (https://azure.microsoft.com/en-us/documentation/articles/active-directory-aadconnect/). There is also a big C# library for communication for MS Azure. Since this non of this is not an option, we'll use the Azure Graph API.

The API is a moving target, but has stable versions that can be used explicitly. We're currently using Version 1.6 of the REST API (see https://msdn.microsoft.com/en-us/Library/Azure/Ad/Graph/api/api-catalog). Other protocols (WS, XML) exist.

Prior to communication with the Azure API, authentication and authorization is done through OAuth2.

After installing the App, a wizard (similar to UCS@school and UCC) will run that will request the UCS user to make some configuration on its behalf. Mainly that is registering and configuring an application in Azure AD. Some of this can be supported pragmatically, some can't...

The wizard must retrieve the following data from the user:
* the client ID
* *TODO*: list all data that is retrieved

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

# Implementation

## Implementation State

Currently there is

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
