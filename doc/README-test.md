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

# Test coverage

* Test cases for ucs-test: 92_office365/*
* Jenkins Job UCS-4.4-2>Product Tests>product-test-component-office365