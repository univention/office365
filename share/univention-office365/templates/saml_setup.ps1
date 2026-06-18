[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Change variables

$entraDomain = '__ENTRA_DOMAIN__'
$keycloakBaseUrl = '__KEYCLOAK_BASE_URL__'
$keycloakRealm = '__KEYCLOAK_REALM__'
$displayName = '__DISPLAY_NAME__'
$samlSigningCertificate = '__SAML_SIGNING_CERTIFICATE__'

# End change

$keycloakBaseUrl = $keycloakBaseUrl.TrimEnd('/')

$samlIssuerUri = "$keycloakBaseUrl/realms/$keycloakRealm"
$samlSignInUri = "$keycloakBaseUrl/realms/$keycloakRealm/protocol/saml"
$samlSignOutUri = "$keycloakBaseUrl/realms/$keycloakRealm/protocol/saml"

Connect-MgGraph -Scopes "Domain.ReadWrite.All", "Directory.ReadWrite.All", "Directory.AccessAsUser.All"

Update-MgDomain -DomainId $entraDomain -AuthenticationType Managed

New-MgDomainFederationConfiguration `
-DomainId $entraDomain `
-DisplayName $displayName `
-ActiveSignInUri $samlSignInUri `
-PassiveSignInUri $samlSignInUri `
-SigningCertificate $samlSigningCertificate `
-IssuerUri $samlIssuerUri `
-SignOutUri $samlSignOutUri `
-PreferredAuthenticationProtocol "saml" `
-FederatedIdpMfaBehavior "acceptIfMfaDoneByFederatedIdp"

Get-MgDomain -DomainId $entraDomain

ECHO "Finished single sign-on configuration change"

PAUSE
