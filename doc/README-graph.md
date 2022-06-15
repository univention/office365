# Microsoft Graph

The Microsoft Graph API is the successor of the former Azure Graph API.
Microsoft kept its new API mostly compatible with its predecessor, but not
entirely. The most obvious difference is the url against which all API calls
have to be performed. It changed from `graph.windows.net` to
`graph.microsoft.com` and each individual call now needs a API version number
as part of the new URL, e.g.

    https://graph.microsoft.com/v1.0/teams/[team_id]/members

Before using the API an access token must be acquired. There are different ways
to get one of these, and they expire automatically after some time. Actually
Microsoft provides with
[msal](https://github.com/AzureAD/microsoft-authentication-library-for-python)
a python library for the log-in process, but we decided against using it.

Our implementation is kept simple in that it can only acquire an access token
by using an application certificate. The token itself is a long string which
appears to be not human readable at first, but turns out to be base64 encoded.
Decoding it on the terminal comes handy for debug sessions:

    echo 'eyJ0...[]' | base64 -d

The log-in works slightly different for Graph, than it did for Azure:

* the directory_id became optional

* the url contains a version number and makes the tenant_id superfluous (because
  it is also contained in the certificate)

* the scope parameter [has to be adjusted](https://docs.microsoft.com/en-us/
  graph/migrate-azure-ad-graph-authentication-library#migrating-to-msal).

* the return value contains a relative time for `expires_in` rather than an
  absolute time `expires_at`.

* a token for Azure cannot be used with Graph.

The actual API access is mostly consistent: There is always the request url
(see above) and then either an empty payload or JSON in the request and the
answer has either an empty body or JSON, but always a http status code, which
is well defined in the Microsoft documentation and only a very few calls have
more than one success value. All calls however return errors one and the same
[list](https://docs.microsoft.com/en-us/graph/errors), which makes a generic
call to catch these very appealing.

A further aspect of development with the Graph API is, that [pagination works
slightly different](https://docs.microsoft.com/en-us/graph/paging).

# Miscrosoft Graph API connector design

## Main Classes
### Listeners
#### User Listener
New implementation of the Listener with the high-level API.  
https://docs.software-univention.de/developer-reference-5.0.html#listener:handler:42  
Receives the dn of the object that has been modified in LDAP, as well as the old and new version of the modified object.  
In the new API a method of the Listener class is re-implemented for each possible operation on the object: modify, delete, add....  
The Listener is in charge of converting the old and new dictionaries that represent a state of an LDAP object into their homonyms as UDM Objects.  
The Listener contains an instance of the Connector class which in turn implements the logic necessary for the interaction between UDM objects and Azure objects.  


#### User Group
New implementation of the Listener with the high level API.  
https://docs.software-univention.de/developer-reference-5.0.html#listener:handler:42  
Identical behavior to the Use Listener but for LDAP Group type objects.

### UDM Objects


# Microsoft Teams

For the new teams API we will require new permissions from the Wizard to be
set: `Group.ReadWrite.All`. This is done manually for now.

## Comparison between Groups and Teams

Microsoft teams is conceptionally very similar to Microsoft Groups and can be
described as a [different kind of group](https://support.microsoft.com/en-us/topic/learn-about-microsoft-365-groups-b565caa1-5c40-40ef-9915-60fdb2d97fa2).

* Groups remain the recommend way to connect with others in a classic (as in
  Exchange) fashion: By having a shared calendar and communication via Email.

* Teams share a common Chat-environment and team work is done within embedded applications.
  (This Video)[https://www.microsoft.com/en-us/videoplayer/embed/RWeqWA?pid=ocpVideo0-innerdiv-oneplayer&postJsllMsg=true]
  helps to showcase how the teams interface looks like and descibes its main functionities superficially.

The [Microsoft documentation](https://docs.microsoft.com/en-us/microsoftteams/office-365-groups#how-microsoft-365-groups-work-with-teams)
says about that:

> When you create a team, a Microsoft 365 group is created to manage team membership.

That said it is obvious, that a Group and a Team can coexist independently from
each other even if they have some functionality in common.


Differences between groups and teams:

|                 | group       | team          |
| -               | -           | -             |
| Membership type | Assigned    | Assigned      |
| Source          | Cloud       | Cloud         |
| Type            | Security    | Microsoft 365 |
| Object Id       | ?           | ?             |
| Creation date   | ?           | ?             |
| Email           | [undefined] | mandatory     |
| Owner           | optional    | mandatory     |



## The team owner

Only users with a certain subscribtion can become team owners. They can be
identified by having the `"service": "TeamspaceAPI"` assigned to them
under `assignedPlans`. A user object could look similar to:

```
                {
                        "signInNames": [],
                        "mailNickname": "ad_test",
                        "postalCode": null,
                        "surname": "ad_test",
                        "userState": null,
                        "passwordProfile": null,
                        "assignedLicenses": [],
                        "lastDirSyncTime": null,
                        "userPrincipalName": "ad_test@office365.dev-univention.de",
                        "passwordPolicies": null,
                        "consentProvidedForMinor": null,
                        "userType": "Member",
                        "usageLocation": "DE",
                        "objectType": "User",
                        "city": null,
                        "assignedPlans": [
                                {
                                        "capabilityStatus": "Deleted",
                                        "assignedTimestamp": "2020-12-15T11:59:33Z",
                                        "servicePlanId": "76846ad7-7776-4c40-a281-a386362dd1b9",
                                        "service": "ProcessSimple"
                                },
                                [...]
                                {
                                        "capabilityStatus": "Deleted",
                                        "assignedTimestamp": "2020-12-15T11:59:33Z",
                                        "servicePlanId": "57ff2da0-773e-42df-b2af-ffb7a2317929",
                                        "service": "TeamspaceAPI"
                                },
                                {
                                        "capabilityStatus": "Deleted",
                                        "assignedTimestamp": "2020-12-15T11:59:33Z",
                                        "servicePlanId": "bea4c11e-220a-4e6d-8eb8-8ea15d019f90",
                                        "service": "RMSOnline"
                                },
                                {
                                        "capabilityStatus": "Deleted",
                                        "assignedTimestamp": "2020-12-15T11:59:33Z",
                                        "servicePlanId": "5136a095-5cf0-4aff-bec3-e84448b38ea5",
                                        "service": "exchange"
                                },
                                {
                                        "capabilityStatus": "Deleted",
                                        "assignedTimestamp": "2020-12-15T11:59:33Z",
                                        "servicePlanId": "5dbe027f-2339-4123-9542-606e4d348a72",
                                        "service": "SharePoint"
                                },
                        ],
                        "objectId": "12f89ccf-34b1-4a69-987a-8a5cd30cb2dd",
                        "showInAddressList": null,
                        "facsimileTelephoneNumber": null,
                        "creationType": null,
                        "state": null,
                        "streetAddress": null,
                        "userStateChangedOn": null,
                        "legalAgeGroupClassification": null,
                        "department": null,
                        "mail": "ad_test@office365.dev-univention.de",
                        "preferredLanguage": null,
                        "accountEnabled": true,
                        "userIdentities": [],
                        "refreshTokensValidFromDateTime": "2020-02-07T03:45:02Z",
                        "companyName": null,
                        "jobTitle": null,
                        "isCompromised": null,
                        "immutableId": "ODg0OTRkODItZGQ3NC0xMDM5LTkxZjctMzUwODA2MjMxMmRl",
                        [...]
```

Note that a user without these permissions does not have any content under
assignedPlans, whereas a user who had the permission at some point in time has
the permission `Deleted` as in this example. Only users with an `Enabled`
permission can become team owners.

Our tests have been able to create users with all necessary permissions in the
past. We have plenty of users prefixed with `zzz_deleted` in our directory,
because we were not able to delete them. Most of these deleted users have had
the correct permissions.

## Examples requests to illustrate differences between groups and teams

Here comes a successful return value after a team was created:

```json
{
        "x-ms-ags-diagnostic": "{\"ServerInfo\":{\"DataCenter\":\"West Europe\",\"Slice\":\"SliceC\",\"Ring\":\"5\",\"ScaleUnit\":\"002\",\"RoleInstance\":\"AGSFE_IN_81\"}}",
        "Content-Length": "0",
        "Content-Location": "/teams('d772b2ae-94ba-4f65-bd8a-c3b26a29a8d8')",
        "request-id": "68644b63-e6ad-4990-a2d1-67db06516bf0",
        "Strict-Transport-Security": "max-age=31536000",
        "client-request-id": "68644b63-e6ad-4990-a2d1-67db06516bf0",
        "Location": "/teams('d772b2ae-94ba-4f65-bd8a-c3b26a29a8d8')/operations('f60c891c-80b6-412e-822d-6dbef28350f3')",
        "Cache-Control": "private",
        "Date": "Mon, 01 Mar 2021 10:39:01 GMT",
        "Content-Type": "text/plain"
}
```
Note, that the `Location` contains the new teams id (in the string behind
'teams') together with the id of the the new channel (behind 'operations')


In comparison: Here comes the return value, when a group is created:

```json
{
        "odata.type": "Microsoft.DirectoryServices.Group",
        "displayName": "testgroupazure",
        "description": "Azuretestgruppe",
        "objectId": "573ae468-5a74-4e74-a1d0-3cdaacd14519",
        "deletionTimestamp": null,
        "onPremisesSecurityIdentifier": null,
        "provisioningErrors": [],
        "odata.metadata": "https://graph.windows.net/3e7d9eb5-c3a1-4cfc-892e-a8ec29e45b77/$metadata#directoryObjects/@Element",
        "lastDirSyncTime": null,
        "onPremisesNetBiosName": null,
        "securityEnabled": true,
        "mailNickname": "testgroupazure",
        "proxyAddresses": [],
        "dirSyncEnabled": null,
        "onPremisesDomainName": null,
        "mail": null,
        "mailEnabled": false,
        "onPremisesSamAccountName": null,
        "objectType": "Group"
}
```

## create a team out of a group

There is also an API call to create a team out of a group. Does that mean, that
we can store a single value to save either group and team on our side?

When we create a team out of the group `573ae468-5a74-4e74-a1d0-3cdaacd14519`,
we get:

```json
{
        "x-ms-ags-diagnostic": "{\"ServerInfo\":{\"DataCenter\":\"West Europe\",\"Slice\":\"SliceC\",\"Ring\":\"5\",\"ScaleUnit\":\"002\",\"RoleInstance\":\"AGSFE_IN_32\"}}",
        "Content-Length": "0",
        "request-id": "384579f5-2d3d-4e1c-9ea0-3ddc4dfda5eb",
        "Strict-Transport-Security": "max-age=31536000",
        "client-request-id": "384579f5-2d3d-4e1c-9ea0-3ddc4dfda5eb",
        "Location": "/teams('573ae468-5a74-4e74-a1d0-3cdaacd14519')/operations('44d88dd0-f410-4508-8f24-b02f3774913a')",
        "Cache-Control": "private",
        "Date": "Mon, 01 Mar 2021 11:19:41 GMT",
        "Content-Type": "text/plain"
}
```
Note how this team has the same id as the group. The object is located under
/teams. This makes the object unique to a team, so that a team can have
different properties to it, than a group.

Let us compare the different properties:

A group object (` ./terminaltest.py --get_group 573ae468-5a74-4e74-a1d0-3cdaacd14519 ''`)
```json
{
        "mailNickname": "testgroupazure",
        "securityIdentifier": "S-1-12-1-1463477352-1316248180-3661418657-424006060",
        "classification": null,
        "deletedDateTime": null,
        "renewedDateTime": "2021-03-01T10:42:43Z",
        "id": "573ae468-5a74-4e74-a1d0-3cdaacd14519",
        "onPremisesProvisioningErrors": [],
        "membershipRuleProcessingState": null,
        "preferredLanguage": null,
        "expirationDateTime": null,
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#groups/$entity",
        "theme": null,
        "preferredDataLocation": null,
        "mail": null,
        "isAssignableToRole": null,
        "onPremisesSamAccountName": null,
        "onPremisesLastSyncDateTime": null,
        "description": "Azuretestgruppe",
        "securityEnabled": true,
        "proxyAddresses": [],
        "creationOptions": [],
        "visibility": null,
        "displayName": "testgroupazure",
        "groupTypes": [],
        "resourceProvisioningOptions": [
                "Team"
        ],
        "onPremisesSyncEnabled": null,
        "createdDateTime": "2021-03-01T10:42:43Z",
        "membershipRule": null,
        "onPremisesNetBiosName": null,
        "resourceBehaviorOptions": [],
        "onPremisesSecurityIdentifier": null,
        "onPremisesDomainName": null,
        "mailEnabled": false
}
```

A team object with the same id (`./terminaltest.py --get_team 573ae468-5a74-4e74-a1d0-3cdaacd14519`)
```json
{
        "classification": null,
        "memberSettings": {
                "allowAddRemoveApps": true,
                "allowDeleteChannels": true,
                "allowCreateUpdateChannels": true,
                "allowCreatePrivateChannels": true,
                "allowCreateUpdateRemoveTabs": true,
                "allowCreateUpdateRemoveConnectors": true
        },
        "displayName": "testgroupazure",
        "description": "Azuretestgruppe",
        "internalId": "19:21ebad242b104f4681822134f31f3d16@thread.tacv2",
        "createdDateTime": "2021-03-01T11:19:41.233Z",
        "webUrl": "https://teams.microsoft.com/l/team/19:21ebad242b104f4681822134f31f3d16%40thread.tacv2/conversations?groupId=573ae468-5a74-4e74-a1d0-3cdaacd14519&tenantId=3e7d9eb5-c3a1-4cfc-892e-a8ec29e45b77",
        "guestSettings": {
                "allowCreateUpdateChannels": false,
                "allowDeleteChannels": false
        },
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#teams/$entity",
        "messagingSettings": {
                "allowTeamMentions": true,
                "allowOwnerDeleteMessages": true,
                "allowUserDeleteMessages": true,
                "allowChannelMentions": true,
                "allowUserEditMessages": true
        },
        "visibility": "public",
        "isArchived": false,
        "isMembershipLimitedToOwners": false,
        "funSettings": {
                "allowStickersAndMemes": true,
                "allowGiphy": true,
                "giphyContentRating": "moderate",
                "allowCustomMemes": true
        },
        "discoverySettings": {
                "showInTeamsSearchAndSuggestions": true
        },
        "id": "573ae468-5a74-4e74-a1d0-3cdaacd14519",
        "specialization": "none"
}
```

It becomes clear, that a team and a group are different object types, even
though they can share the same Id.


## Getting started with `terminaltest.py`

If calling terminaltest.py leads to an error like `Application with identifier
'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' was not found in the directory` that is
probably the case, because a wrong connection was automatically pre-selected.
Check which connections exist on your system and choose another, like so:

```
root@master:~/office365# ./terminaltest.py -a
[
    "o365domain",
    "u-azure-test-de",
    "defaultADconnection",
    "azuretestdomain",
    "o365-dev-univention-de"
]
root@master:~/office365# ./terminaltest.py -g azuretestdomain
DEBUG:office365:adconnection_alias='azuretestdomain'
DEBUG:office365:adconnection_alias='azuretestdomain'
INFO:office365:proxy settings: {}
INFO:office365:service_plan_names=['SHAREPOINTWAC', 'SHAREPOINTWAC_DEVELOPER', 'OFFICESUBSCRIPTION', 'OFFICEMOBILE_SUBSCRIPTION', 'SHAREPOINTWAC_EDU']
```
