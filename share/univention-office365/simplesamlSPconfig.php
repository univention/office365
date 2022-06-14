<?php
$metadata['urn:federation:MicrosoftOnline'] = array(
	'AssertionConsumerService'	=> array('https://login.microsoftonline.com/login.srf'),
	'SingleLogoutService'	=> array('https://login.microsoftonline.com/common/saml2'),
	'NameIDFormat'	=> 'urn:oasis:names:tc:SAML:2.0:nameid-format:persistent',
	'simplesaml.nameidattribute'	=> 'entryUUID',
	'simplesaml.attributes'	=> true,
	'attributes'	=> array('entryUUID', 'univentionOffice365userPrincipalName', 'univentionOffice365Enabled'),
	'OrganizationName'	=> 'Microsoft 365',
	'signature.algorithm' => 'http://www.w3.org/2000/09/xmldsig#rsa-sha1',
	'authproc' => array(
		10 => array(
			'class' => 'authorize:Authorize',
			'regex' => FALSE,
			'univentionOffice365Enabled' => '1',
		),
		50 => array(
			'class' => 'core:AttributeMap',
			'univentionOffice365userPrincipalName' => 'IDPEmail',
		),
		60 => array(
			'class' => 'core:PHP',
			'code' => '
				$entryuuid = base64_encode($attributes["entryUUID"][0]);
				$attributes["entryUUID"] = array($entryuuid);
				',
		),
		65  => array(
			'class' => 'saml:AttributeNameID',
			'attribute' => 'entryUUID',
			'Format' => 'urn:oasis:names:tc:SAML:2.0:nameid-format:persistent',
		),
		70 => array(
			'class' => 'core:AttributeLimit',
			'IDPEmail'
		    ),
	),
);
