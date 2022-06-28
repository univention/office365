# Microsoft 365 connector

Azure is the Microsoft cloud service. It has a so-called Active Directory (Azure AD) component, that can manage Users, Groups, Applications, Roles, Permissions etc. We need it to manage users, groups, logins and Office365 licences.

This package provides functionality to synchronize UCS user and group accounts
to Azure AD to provision Microsoft 365 accounts for them.
The accounts can be configured for synchronization to multiple Azure AD domains.

This package contains a UMC wizard, extended attributes and hooks for user and
group accounts and listener modules to do the actual synchronization.

The package is the basis for the Office365 App available in the UCS App Center,
which can only be installed on UCS Systems with role Primary Directory Node or Backup Directory Node.

* Credentials for testing accounts: https://hutten.knut.univention.de/dokuwiki/externe_konten:office365
* Web-Interfaces:
  * Microsoft Azure services: https://portal.azure.com/
  * Microsoft Teams services: https://admin.teams.microsoft.com (for Teams)

## User Story

1. After installation of this app, UCS user accounts have a new tab *Microsoft 365*
   in UMC, which offers a checkbox to *Enable the Synchronization of the account
   to an Azure Active Directory*. Below that checkbox, the "alias" name of a
   target Azure AD can be selected. If none is selected, then a default
   specified via UCR variable `office365/defaultalias` will be selected.
1. Before synchronization can start to work, an app specific wizard needs to be
   run to configure (or "initialize") the Azure AD Connection.
   The UCR variable `office365/adconnection/wizard` specifies the alias name
   of the Azure AD Connection that it will configure.
1. AD Connections are represented as UDM `office365/ad-connection` objects and
  also visible in UCR below `office365/adconnection/alias/`.
1. Multi-Connection support has been added in app version 3.0. Migration from
   earlier app versions is automatic, but can optionally be disabled via the UCR
   variable `office365/migrate/adconnectionalias`. The automatic migration
   migrates the existing initialized AD Connection to `defaultADconnection`,
   by creating a UDM object of type `office365/ad-connection` and setting the
   UCR variable: `office365/adconnection/alias/defaultADconnection`.
   Optionally the migration can be started manually at a later stage by running
   the command
   `/usr/share/univention-office365/scripts/migrate_to_adconnectionalias`
1. Group synchronization doesn't happen by default. The UCR variable
   `office365/groups/sync` needs to activated for this. After changing that
   UCR variable the Univention Directory Listener needs to be restarted.
   Group synchronization may put some load on the server, because the selection
   of which groups to synchronize happens automatically, by checking nested group
   memberships of user accounts that are enabled for synchronization.
1. In LDAP, enabled user accounts are marked by the attribute
   `univentionOffice365Enabled`. The target Azure ADs can be seen in the
   multivalued LDAP attribute `univentionOffice365ADConnectionAlias`.
   After successful synchronization, the listener modules stores the
   Azure AD object IDs at the corresponding UCS user and group objects.
   These object IDs are specific for each target Azure AD instance.
   This information is used for internal bookkeeping and not easily accessible
   via LDAP search, because it is stored encoded as `base64(zipped(json(dict)))`
   in an LDAP attribute `univentionOffice365Data`. For user objects this
   encoded dictionary additionally includes the Azure AD specific *userPrincipalNames*,
   which are visible in the UMC users/user tab *Microsoft 365*. Their presence
   in the UMC provides the possibility to quickly check, if the initial
   synchronization of an account has been successful.
1. The connector is able to configure Office 365 subscriptions at user objects. Subscriptions are
   only assigned when a user is enabled for Azure synchronization. Re-enabling a user also
   configures subscriptions. By default, it is tried to enable a subscription with the
   following Azure-internal identifiers:
   `SHAREPOINTWAC`, `SHAREPOINTWAC_DEVELOPER`, `OFFICESUBSCRIPTION`.
   The default can be overruled by the UCR variable `office365/subscriptions/service_plan_names`. To see
   available subscriptions, use the tool `print_subscriptions`.
   Fine-grained subscription policies can be set with UDM objects of the type
   *office365/profile*. Here, a subscription name and individually white or blacklisted
   service plans can be configured. These profiles can be set at UDM groups/group objects.
   When a member of such a group is enabled for synchronization, the user listener will
   search for the first group where an `office365/profile` is set, and configure the Azure
   user object accordingly.
1. It is possible to use external office clients with the connector, like mobile apps
   or office desktop products. A respective subscription / service plan is required in Azure.
   These external programs need their activation tokens reset in a 90-day period, or will
   require frequent (multiple per hour) logins with Azure credentials to continue working.
   A cronjob exists which calls `o365_usertokens`, to reset these tokens in a configurable
   interval. After the tokens for a user are reset, the user has to re-authenticate once.
1. The connector never synchronizes the user password hash. A SAML service provider is configured
   to handle login against the UCS SAML Identity Provider. When configuring multiple AD
   connections, additional SAML SPs (service providers) have to be configured as per documentation. To
   configure the SAML connection, the wizard offers a powershell script that has to be
   executed on an Microsoft Windows operating system.

## Admin/User Documentation

* http://docs.software-univention.de/manual.html#idmcloud:o365

# Developer Documentation
Multiple files are available for developers:
* Internal code design and description: [README-code.md](/doc/README-code.md)
* Package build process: [README-build.md](/doc/README-build.md)
* Description of the implemented tests: [README-test.md](/doc/README-test.md)
* Continuous Integration with GitLab [README-CI.md](/doc/README-CI.md)
* Tools to check and debug [README-tools.md](/doc/README-tools.md)

# TODO

* Microsoft Label in GitLab [issues](https://git.knut.univention.de/univention/ucs/-/issues/?sort=updated_desc&state=opened&label_name%5B%5D=App%3A%3AMicrosoft%20365&label_name%5B%5D=Status%3A%3ANew).
* Office 365 component in [Bugzilla](https://forge.univention.org/bugzilla/buglist.cgi?component=Office%20365&list_id=180237&product=UCS&resolution=---).
