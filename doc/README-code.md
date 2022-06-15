  * [Design Principles](#design-principles)
    + [Modules](#modules)
      - [UDM Wrapper](#udm-wrapper)
      - [Microsoft](#microsoft)
      - [Connector](#connector)
    + [Utils](#utils)
      - [UCR Helper](#ucr-helper)
      - [UDM Helper](#udm-helper)
    + [Information and calls flow](#information-and-calls-flow)
    + [Listeners](#listeners)
    + [UDMWrapper](#udmwrapper)
    + [Microsoft](#microsoft-1)
      - [Core](#core)
      - [Accounts | Tokens | Manifest | JSONStorage](#accounts---tokens---manifest---jsonstorage)
      - [Azure Objects](#azure-objects)
      - [Core | URLs](#core---urls)
      - [Exceptions (core_exceptions, exceptions, login_exceptions)](#exceptions--core-exceptions--exceptions--login-exceptions-)
    + [Connectors](#connectors)
      - [Parser (UDMObjects => AzureObjects)](#parser--udmobjects----azureobjects-)
    + [Helpers](#helpers)
      - [Utils | UCRHelper | UDMHelper](#utils---ucrhelper---udmhelper)
    + [Async Queue/Tasks (Teams operations)](#async-queue-tasks--teams-operations-)
    + [Use cases](#use-cases)
      - [Creation](#creation)
      - [Modification](#modification)
      - [Deletion](#deletion)
  * [Features](#features)
    + [Multi Account support](#multi-account-support)
    + [UCR variables to modify connector behaviour](#ucr-variables-to-modify-connector-behaviour)
      - [werror](#werror)
      - [UDM attribute to sync in Azure (mapping, anonimize, never, multi valued)](#udm-attribute-to-sync-in-azure--mapping--anonimize--never--multi-valued-)
      - [AdConnections (filter, alias, wizard)](#adconnections--filter--alias--wizard-)
      - [UsageLocation (or ssl/country or country ¿st?...)](#usagelocation--or-ssl-country-or-country--st--)
      - [defaultAlias (related with UCM)](#defaultalias--related-with-ucm-)
      - [Group sync](#group-sync)
  * [Async daemon](#async-daemon)
  * [Async calls](#async-calls)
- [Implementation](#implementation)
  * [Implementation State](#implementation-state)
  * [Authorization Code Grant Flow - ***not** used by listener!*](#authorization-code-grant-flow------not---used-by-listener--)
  * [Client credentials flow - *used by listener*](#client-credentials-flow----used-by-listener-)
- [Dependencies / Constraints](#dependencies---constraints)
  * [Teams](#teams)
- [Design](#design)
- [Permission Name: Directory.ReadWrite.All, Type: Application](#permission-name--directoryreadwriteall--type--application)
- [Permission Name: Group.ReadWrite.All, Type: Application](#permission-name--groupreadwriteall--type--application)
- [Permission Name: User.ReadWrite.All, Type: Application](#permission-name--userreadwriteall--type--application)
- [Permission Name: TeamMember.ReadWrite.All, Type: Application](#permission-name--teammemberreadwriteall--type--application)
      - [Objects](#objects)
    + [Async queue](#async-queue)

<small><i><a href='http://ecotrust-canada.github.io/markdown-toc/'>Table of contents generated with markdown-toc</a></i></small>



# Design Principles

The code for this connector is organized into a module called office365 inside the main univention python module.  
All the code and classes have being designed trying to clearly separate the functionality of code related
with UCS and UDM and on the other hand the functionality related with the connection to the Microsoft Graph API.  


```
                         univention.office365
                       ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
                       │                                                                                                        │
                       │                                                                                                        │
                       │       UDMWrapper                Connector                    Microsoft                                 │
                       │      ┌─────────────────────┐   ┌────────────────────────┐   ┌──────────────────────────────────────┐   │
┌─────────────┐        │      │                     │   │                        │   │                                      │   │
│             │        │      │  ┌──────────────┐   │   │   User Connector       │   │                    ┌─────────────┐   │   │
│    User     │        │      │  │              │   │   │  ┌─────────────────┐   │   │    ┌─────────┐     │             │   │   │
│  Listener   │        │      │  │  UDM         │   │   │  │                 │   │   │    │         │     │             │   │   │
│             │        │      │  │  User        │   │   │  │                 │   │   │    │  Azure  │     │             │   │   │
└─────────────┘        │      │  │  Object      │   │   │  │                 │   │   │    │  User   │     │             │   │   │
                       │      │  │              │   │   │  ├──────────┐      │   │   │    │         │     │             │   │   │
                       │      │  └──────────────┘   │   │  │   User   │      │   │   │    └─────────┘     │             │   │   │
                       │      │                     │   │  │  Parser  │      │   │   │                    │             │   │   │
                       │      │                     │   │  └──────────┴──────┘   │   │                    │    Azure    │   │   │
                       │      │  ┌──────────────┐   │   │                        │   │                    │    Core     │   │   │
                       │      │  │              │   │   │                        │   │    ┌─────────┐     │             │   │   │
                       │      │  │  UDM         │   │   │                        │   │    │         │     │             │   │   │
┌─────────────┐        │      │  │  Group       │   │   │                        │   │    │  Azure  │     │             │   │   │
│             │        │      │  │  Object      │   │   │   Group Connector      │   │    │  Group  │     │             │   │   │
│    Group    │        │      │  │              │   │   │  ┌─────────────────┐   │   │    │         │     │             │   │   │
│  Listener   │        │      │  └──────────────┘   │   │  │                 │   │   │    └─────────┘     │             │   │   │
│             │        │      │                     │   │  │                 │   │   │                    └─────────────┘   │   │
└─────────────┘        │      └─────────────────────┘   │  │                 │   │   │                                      │   │
                       │                                │  ├──────────┐      │   │   │                                      │   │
                       │                                │  │  Group   │      │   │   │                                      │   │
                       │                                │  │  Parser  │      │   │   │                                      │   │
                       │                                │  └──────────┴──────┘   │   │                                      │   │
                       │                                │                        │   │                                      │   │
                       │                                └────────────────────────┘   └──────────────────────────────────────┘   │
                       │                                                                                                        │
                       └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

In the middle, a connector classes are being used to connect to the Microsoft Graph API and to the UCS LDAP side.
Only these classes have the needed "knowledge" to connect both sides.

You should be able to use most of the code outside of the listeners.
When modifying code, please keep the separation of where which objects are used.

### Modules
The main module for this connector is `univention.office365`. Several submodules are defined splitting the parts described before.

#### UDM Wrapper
When the listener receives an event from the UCS LDAP side for an action, it receives
the dn of the object, the data of the object before the operation, the data of the object
after the operation and the action. This data of the old and the new object comes as a dictionary.
This dictionary of string keys and bytes values is the processed by the UDM wrapper to get
the representation of the object in a UDM class. The underlying LDAP reference is 
also kept as an attribute of the new UDM class.

This classes are a higher level abstraction of the objects in the LDAP layer.

* UDMOfficeUser
* UDMOfficeGroup

The functionality of this two objects have being extended to take care of the information related with the Microsoft connections/information
of each object.


#### Microsoft

[//]: # (TODO: Check links)
To synchronize an on-premises AD with Azure AD, "Azure AD Connect" can be used (https://azure.microsoft.com/en-us/documentation/articles/active-directory-aadconnect/). There is also a big C# library for communication for MS Azure. Since this non of this is not an option, we'll use the Azure Graph API.

[//]: # (TODO: Check links)
The API is a moving target, but has stable versions that can be used explicitly. We're currently using Version 1.6 of the REST API (see https://msdn.microsoft.com/en-us/Library/Azure/Ad/Graph/api/api-catalog).

While developing this wrapper around the Microsoft Graph API the thinking of keeping it as
independent as possible from the UCS LDAP side was taken into account. This way the `univention.office365.microsoft`
module could be used as an independent module to operate over the Microsoft Graph API.

#### Connector

Until this point classes and methods to work with the data from the UCS/LDAP side and the Microsoft Azure Directory on the other side.

No logic have being described to connect the two sides.

This is the main function of the connector submodule. When the listener receives an action related with an object in the UCS LDAP side,
it's converted to the corresponding UDM Office object and then a specific connector is used
to replicate the operation on the Microsoft Azure Directory side.

Mainly two classes take care of the operations for the Users and Groups:
* UserConnector
* GroupConnector

Both have methods to create, delete and modify this objects. Also, several convenience methods
have being implemented in the connector to take care of some dependencies between these objects (pertences, memberships, ownership, etc).



### Information and calls flow

### Listeners
* Two listeners
* New API (link)


### UDMWrapper
```
                ┌──────────────┐
                │              │
                │   UDMObject  │
                │              │
                └──────┬───────┘
                       │
                       │
                       │
              ┌────────▼──────────┐
              │                   │
              │  UDMOfficeObject  │
              │                   │
              └────────┬──────────┘
                       │
         ┌─────────────┴───────────────┐
         │                             │
┌────────▼────────┐            ┌───────▼──────────┐
│                 │            │                  │
│  UDMOfficeUser  │            │  UDMOfficeGroup  │
│                 │            │                  │
└─────────────────┘            └──────────────────┘
```
* Usage of UDM objects
* Implemented classes 
* Main methods
* Examples of usage of the classes

### Microsoft

```
                                        ┌─────┐
                                        │Token│
                                        └──┬──┘
                                           │
                                           │
                                           │
                                           │
                                           │
                                     ┌─────┴────┐
                                     │     ▼    │               │
                                     │  Azure   │               │
                                     │  Account │               │
        ┌───────┐                    │          │               │
        │Azure  │                    └─────┬────┘               │
        │User  ◄├────────────┐             │                    │
        └───────┘            │             │                    │
                             │             │                    │
       ┌────────┐            │             │                    │                  .-~~~-.
       │ Azure ◄├────────────┤        ┌────┴────┐◄─────────────►│          .- ~ ~-(       )_ _
       │ Group  │            │        │    ▼    │               │         /        Microsoft    ~ -.
       └────────┘            ├────────┤  Azure  │    Requests   │        |         Graph             \
                             │        │  Core   │◄─────────────►│         \        API              .'
     ┌──────────┐            │        │         │               │           ~- . _____________ . -~
     │  Azure   │            │        └─────────┘◄─────────────►│
     │  Team   ◄├────────────┤                                  │
     └──────────┘            │                                  │
                             │                                  │
┌───────────────┐            │                                  │
│               │            │                                  │
│ Azure         │            │                                  │
│ Subscription ◄├────────────┘                                  │
│               │                                               │
└───────────────┘                                               │
                                                                │
                                                                │
                                                                │
```


#### Core

#### Accounts | Tokens | Manifest | JSONStorage

#### Azure Objects

#### Core | URLs

#### Exceptions (core_exceptions, exceptions, login_exceptions)

### Connectors
```
              ┌───────────────────┐       ┌─────────────────────┐
              │                   │       │                     │
              │    Connector      │       │ ConnectorAttributes │
              │                 ◄─┼───────┤                     │
              └────────┬──────────┘       └─────────────────────┘
                       │
         ┌─────────────┴───────────────┐
         │                             │
┌────────▼────────┐            ┌───────▼──────────┐
│                 │            │                  │
│  UserConnector  │            │  GroupConnector  │
│                 │            │                  │
└─────────────────┘            └──────────────────┘
```

#### Parser (UDMObjects => AzureObjects)

### Helpers

#### Utils
Several functions have being implemented to help with the development of the connector.

#### UCR Helper
Univention Configuration Registry Helper. This class is used to get the configuration values from the UCR related to the office365 connector.
Convenience methods are being implemented to get and process the values from the UCR.
Any operation related to UCR for this connector should be implemented in this class.

#### UDM Helper
Univention Directory Manager Helper. This class is used to get the UDM objects related to the office365 connector.
Convenience methods are being implemented to get and process the objects from UDM.
Any operation related to UDM for this connector should be implemented in this class.

### Async Queue/Tasks (Teams operations)
#### Async queue
Some Microsoft API calls are asynchronous. This means that the
call is made, but the response is not returned immediately.

A queue is used to store the `tasks` to be performed. The queue is
shared with another process that will consume the actions and would
execute them.

The queue can be implemented with several backends. The
default is a json file directory containing files for each task.
A Redis backend is also available as an example but not currently used.

The code related to the Async Queue is in `modules/univention/office365/asyncqueue.py`.

#### Async daemon

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

#### Async calls

```
from univention.office365.api_helper import write_async_job
write_async_job(a_function_name='modify_group', a_ad_connection_alias='o365domain', object_id="params", new_name="aaaa", ...)
```


### Use cases

#### Creation

#### Modification

#### Deletion

## Features

### Multi Account support

### UCR variables to modify connector behaviour

#### werror

#### UDM attribute to sync in Azure (mapping, anonimize, never, multi valued)

#### AdConnections (filter, alias, wizard)

#### UsageLocation (or ssl/country or country ¿st?...) 

#### defaultAlias (related with UCM)

#### Group sync


======================================================================================


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



#### Objects
To keep an Object-Oriented approach the classes for the Microsoft Graph API are being organized into
classes representing the objects in the Microsoft Azure Directory service.
* UserAzure
* GroupAzure
* TeamAzure
* SubscriptionAzure

This classes contains the attributes and methods needed to interact with the Microsoft Graph API on a
higher level of abstraction.



UCS
LDAP
change


Listener
receives representation 
of the old and new object
and the operation executed

Creates corresponding UDM objects

Call corresponding Connector Method

--

For each ad connection configured for the UDM object

Resolve the operation logic
(object dependencies, recursivity, ...)

Creates the corresponding Azure Object (parse)

Call the method of the Azure Object

-- 

Prepare data

Call the Graph API with the credentials of the ad connection
through the Core wrapper implementation.




