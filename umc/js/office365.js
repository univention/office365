/*
 * Copyright 2016-2019 Univention GmbH
 *
 * http://www.univention.de/
 *
 * All rights reserved.
 *
 * The source code of this program is made available
 * under the terms of the GNU Affero General Public License version 3
 * (GNU AGPL V3) as published by the Free Software Foundation.
 *
 * Binary versions of this program provided by Univention to you as
 * well as other copyrighted, protected or trademarked materials like
 * Logos, graphics, fonts, specific documentations and configurations,
 * cryptographic keys etc. are subject to a license agreement between
 * you and Univention and not subject to the GNU AGPL V3.
 *
 * In the case you use this program under the terms of the GNU AGPL V3,
 * the program is provided in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public
 * License with the Debian GNU/Linux or Univention distribution in file
 * /usr/share/common-licenses/AGPL-3; if not, see
 * <http://www.gnu.org/licenses/>.
 */
/*global require,define,window,setTimeout,dojo*/

define([
	"dojo/_base/declare",
	"dojo/_base/lang",
	"dojo/_base/array",
	"dojo/aspect",
	"dojo/dom-construct",
	"dojo/Deferred",
	"umc/tools",
	"umc/dialog",
	"umc/widgets/Module",
	"umc/widgets/Wizard",
	"umc/widgets/Text",
	"umc/widgets/TextBox",
	"umc/widgets/Button",
	"umc/widgets/Uploader",
	"umc/widgets/ProgressBar",
	"umc/i18n!umc/modules/office365",
	"xstyle/css!./office365.css"
], function(declare, lang, array, aspect, domConstruct, Deferred, tools, dialog, Module, Wizard, Text, TextBox, Button, Uploader, ProgressBar, _) {

	var OfficeWizard = declare('umc.modules.office365.OfficeWizard', [Wizard], {

		_uploadDeferred: null,
		autoValidate: true,
		autoFocus: false,
		authorizationurl: null,

		constructor: function() {
			this.inherited(arguments);
			this.origin = window.location.protocol + '//' + window.location.host + (window.location.port ? ':' + window.location.port : '');
			if (!this.switchPage) { // function added by Bug #41081. Can be removed in UCS 4.2
				this.switchPage = lang.hitch(this, function(pageName) {
					this._updateButtons(pageName);
					this.selectChild(this._pages[pageName]);
					window.scrollTo(0, 0);
				});
			}

			lang.mixin(this, {
				pages: [{
					name: 'start',
					headerText: _('Welcome to the Office 365 configuration'),
					helpText: _('Welcome to the Microsoft Office 365 setup wizard. A few steps are needed to complete the configuration process.'),
					widgets: [{
						type: Text,
						name: 'already-initialized',
						content: _('<b>Warning!</b> The configuration has already been done. If you continue, the current connection settings will be replaced.'),
						visible: false
					}, {
						type: Button,
						name: 'single-sign-on',
						visible: false,
						label: _('Open single sign-on configuration instructions'),
						callback: lang.hitch(this, function() {
							this.switchPage('single-sign-on-setup');
						})
					}, {
						type: Text,
						name: 'info',
						content: this.getTextWelcome()
					}]
				}, {
					name: 'add-application',
					headerText: _('Create an application for Office 365'),
					helpText: _('To allow UCS to synchronize selected user accounts a new application have to be added in the active directory.'),
					widgets: [{
						name: 'infos',
						type: Text,
						content: this.getTextConfiguration()
					}, {
						type: TextBox,
						name: 'login-url',
						sizeClass: 'Two',
						readOnly: true,
						label: _('SIGN-ON URL')
					}, {
						name: 'complete',
						type: Text,
						content: this.formatOrderedList([_('Complete the wizard in the Azure portal by clicking the <i>Register</i> button.')], {start: 9})
					}]
				}, {
					name: 'ucs-integration',
					headerText: _('Connect Azure with UCS'),
					helpText: _('To integrate Office 365 into UCS the manifest of the new application has to be downloaded.') + ' ' + _('The manifest is a JSON file which contains all necessary information required to connect UCS with your active directory.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextUCSIntegration()
					}, {
						type: TextBox,
						name: 'adconnection_id',
						label: _('Federation metadata document'),
						placeHolder: _('Please insert the federation metadata document URL here...'),
						sizeClass: 'Two',
						required: true,
						value: '',
						onChange: lang.hitch(this, function(value) {
							this.getWidget('manifest-upload', 'upload').set('dynamicOptions', {
								adconnection_id: value,
								domain: this.getWidget('manifest-upload', 'domain').get('value')
							});
						})
					}, {
						type: Text,
						name: 'infosbottom',
						content: this.getTextUCSIntegrationBottom()
					}, {
						type: Text,
						name: 'continue',
						content: this.formatOrderedList([_('Continue by clicking on <i>Next</i>.')], {start: 7})
					}]
				}, {
					name: 'manifest-upload',
					headerText: _('Upload manifest to UCS'),
					helpText: _('The manifest is a JSON file which contains all necessary information required to connect UCS with your active directory.'),
					widgets: [{
						type: Text,
						name: 'domaininfo',
						content: this.getTextManifestUploadDomain()
					}, {
						type: TextBox,
						name: 'domain',
						label: _('Verified domain name'),
						required: true,
						placeHolder: _('domain name (e.g. univention.de)'),
						onChange: lang.hitch(this, function(value) {
							this.getWidget('manifest-upload', 'upload').set('dynamicOptions', {
								adconnection_id: this.getWidget('ucs-integration', 'adconnection_id').get('value'),
								domain: value
							});
						})
					}, {
						type: Text,
						name: 'infos',
						content: this.getTextManifestUpload()
					}, {
						type: Uploader,
						name: 'upload',
						buttonLabel: _('Upload manifest'),
						command: 'office365/upload',
						dynamicOptions: {
							adconnection_id: 'common',
							domain: ''
						},
						onUploadStarted: lang.hitch(this, function() {
							this._uploadDeferred = new Deferred();
							this.standbyDuring(this._uploadDeferred);
							this._uploadDeferred.then(lang.hitch(this, 'manifestUploaded'));
						}),
						onUploaded: lang.hitch(this, function(result) {
							this._uploadDeferred.resolve(result);
						}),
						onError: lang.hitch(this, function(error) {
							this._uploadDeferred.reject(error);
						})
					}]
				}, {
					name: 'upload-manifest',
					headerText: _('Upload updated manifest'),
					helpText: _('UCS modified the manifest to include all information which Azure needs to accept connections from UCS. The modified manifest now has to be uploaded to Azure.'),
					widgets: [{
						type: Text,
						name: 'azure-integration',
						content: this.getTextUpdateManifest()
					}]
				}, {
					name: 'authorize',
					headerText: _('Authorize UCS Office 365 application'),
					helpText: _('In the following step some permissions have to be granted to UCS.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextAzureAuthorization()
					}, {
						type: Text,
						name: 'image',
						content: this.getTextAzureAuthorizationImage()
					}],
					buttons: [{
						name: 'authorize',
						label: _('Authorize UCS to access application'),
						callback: lang.hitch(this, 'openAuthorization')
					}],
					layout: ['infos', 'authorize', 'image']
				}, {
					name: 'single-sign-on-setup',
					headerText: _('Single Sign-On setup'),
					helpText: _('The UCS SAML identity provider has to be connected to Azure by running a Windows Powershell script.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextSingleSignOnSetup()
					}]
				}, {
					name: 'success',
					headerText: _('Office 365 setup complete'),
					helpText: _('Congratulations, the connection between UCS and Microsoft Azure has been established.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextSuccessPage1()
					}]
				}, {
					name: 'success2',
					headerText: _('Office 365 setup complete'),
					helpText: _('The configuration of synchronized attributes can be done via Univention Config Registry.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextUniventionConfigRegistry()
					}]
				}, {
					name: 'success3',
					headerText: _('Office 365 setup complete'),
					helpText: _('Users can now single sign on into the Office 365 account.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('Synchronized users can log into Office 365 by using the link on the <a href="/univention/" target="_blank">UCS portal</a>.') + '<br>' + this.img(_('sso-login_EN.png'))
					}]
				}, {
					name: 'error',
					headerText: _('An error occurred'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'error',
						content: _('An error occurred. It might help to restart the wizard.')
					}]
				}]
			});
			array.forEach(this.pages, function(page) {
				page['class'] = 'umc-office365-page umc-office365-page-' + page.name;
			});
		},

		postCreate: function() {
			this.inherited(arguments);

			// prevent that one doesn't upload the file by just pressing enter
			this._pages['manifest-upload']._form.onSubmit = function(e) {
				if (e) { e.preventDefault(); }
				return false;
			};

			tools.forIn(this._pages, function(name, page) {
				page.addChild(new Text({
					'class': 'umcPageIcon',
					region: 'nav'
				}));
			});
		},

		getTextWelcome: function() {
			return this.formatParagraphs([
				_('Welcome to the <a href="https://products.office.com/" target="_blank">Microsoft Office 365</a> setup wizard.'),
				_('It will guide you through the process of setting up automatic provisioning of Microsoft Office 365 accounts for your user accounts.'),
				_('To use this app you need a Microsoft Office 365 admin account, a global administrator account in the corresponding Azure AD and a <a href="https://azure.microsoft.com/en-us/documentation/articles/active-directory-add-domain/" target="_blank">verified domain</a>.'),
				_('In addition, a Windows PC with at least Windows 7 is required to configure single sign-on for this domain.')
			]);
		},

		getTextConfiguration: function() {
			return _('Please follow the next steps to create a new application in the Azure active directory:') + this.formatOrderedList([
				_('Login to the <a href="https://portal.azure.com/" target="_blank">Microsoft Azure portal</a>.'),
				_('Select the Azure Active Directory service. In case you have multiple Active Directories, click <i>Switch directory</i> to choose the one you wish to synchronize with UCS.') + this.img(_('AAD.png')),
				_('Open the <i>APP REGISTRATIONS</i> module.') + this.img(_('app_registrations_EN.png')),
				_('If existing applications are not shown, select <i>All applications</i> above the search field.'),
				_('Click <i>NEW REGISTRATION</i> to add a new application to your directory.') + this.img(_('top_bar_add_app_EN.png')),
				_('Enter a name for your application, e.g. <i>UCS Office 365</i>.'),
				_('As supported account type select <i>Accounts in this organizational directory only</i>.') + this.img(_('app_name_EN.png')),
				_('In the category <i>Redirect URI</i>, make sure <i>Web</i> is selected in the dropdown. Copy the value below and paste it into the textfield in the Azure wizard.')
			]);
		},

		getTextUCSIntegration: function() {
			return this.formatOrderedList([
				_('Make sure the newly created application is selected or open it by clicking on it.'),
				_('On the app <i>Overview</i>, click on <i>ENDPOINTS</i>.') + this.img(_('endpoints_EN.png')),
				_('Copy the value for <i>FEDERATION METADATA DOCUMENT</i>.') + this.img(_('copy_adconnection_id_EN.png')),
				_('Insert the copied value into the text box below.')
			]);
		},

		getTextUCSIntegrationBottom: function() {
			return this.formatOrderedList([
				lang.replace(_('Download the {link} which is used to prove the application’s identity when requesting a token.'), {link: '<a href="/univention/command/office365/o365_public_signing_cert.pem" target="_blank">' + _('public certificate key') + '</a>'}),
				_('In the <i>Certificate & secrets</i> section, click on <i>Upload certificate</i> and select the certificate file that was downloaded in the above step. Click on <i>Add</i> to add the certificate to the Azure app.') + this.img(_('upload_certificate_EN.png')),
				_('In the <i>Manage</i> section, select <i>MANIFEST</i> and then <i>DOWNLOAD</i> on the top. The manifest file will be downloaded onto your computer.') + this.img(_('manage_manifest_EN.png')),
			], {start: 4});
		},

		getTextManifestUploadDomain: function() {
			return _('The setup wizard now needs the domain that was verified during the configuration of the Office 365 account. Insert it into the text box below.');
		},

		getTextManifestUpload: function() {
			return _('Please upload the manifest that you just downloaded from the Azure Portal by using the upload button below. (The downloaded manifest is a file with the same name as the app and ends in ".json".)') + ' ' + _('After uploading the manifest you will be offered to download a file <i>manifest.json</i>. Store this file on your computer.');
		},

		getTextUpdateManifest: function() {
			return this.formatOrderedList([
				_('If the download of the <i>manifest.json</i> file didn\'t start automatically <a download="manifest.json" href="/univention/command/office365/manifest.json" target="_blank">click here</a>.'),
				_('Select your app, <i>MANIFEST</i> and <i>UPLOAD</i> the manifest in the Azure dashboard.'),
				_('To upload the manifest in the panel click on <i>SELECT A FILE</i> and choose the previously downloaded <i>manifest.json</i>. Click on <i>Save</i> to complete the upload.') + this.img(_('azure_upload_manifest_window_EN.png')),
				_('After the upload has succeeded, select the <i>API permissions</i> section.') + this.img(_('required_perms_btn_EN.png')),
				_('The permissions have already been configured by the manifest. Click the <i>Grant admin consent for ...</i> button and <i>Yes</i> in the following dialog.') + this.img(_('grant_perms_EN.png')) + this.img(_('grant_perms_yes_EN.png')),
				_('After the permission granting has succeeded continue this wizard by clicking on <i>Next</i>.')
			]);
		},

		getTextAzureAuthorization: function() {
			return [_('The connection between UCS and the Microsoft Azure application has to be authorized now.'),
				_('When you click on the button below a a new browser window will be opened. Please select your account and log in if necessary and click on <i>Accept</i> to permit the permission request.'),
				_('After this the browser window will close itself and the connection between UCS and the Office 365 application will be established.')
			].join(' ');
		},

		getTextAzureAuthorizationImage: function() {
			return this.img(_('ms_authorize_screen_text_and_image_EN.png'));
		},

		getTextSingleSignOnSetup: function() {
			return '<p>' + _('To finish configuration, single sign-on has to be configured for the Office 365 domain. Microsoft only supports to configure single sign-on by running a Microsoft Powershell script on a Windows PC.') + '</p>' + this.formatOrderedList([
				_('If you open this setup wizard again at a later time, a link on the first page will take you back to this instructions.'),
				_('To use the single sign-on script, your Windows PC must have at least installed the <a href="%s" target="_blank">.NET runtime environment version 4.5.1.</a>.', _('https://www.microsoft.com/download/details.aspx?id=40779')),
				_('Install the latest version of Microsoft Powershell, at least <a href="%s" target="_blank">Windows Management Framework 5.1</a> has to be installed.', _('https://aka.ms/wmf5download')),
				_('On your Windows PC, follow the <a href="%s" target="_blank">instructions from Microsoft PowerShell Gallery</a> to install the <i>Microsoft Online Services PowerShell for Azure Active Directory</i> module.', _('https://www.powershellgallery.com/packages/MSOnline')),
				_('Make sure that the verified domain which is set up in Azure Active Directory is <b>not</b> configured as the primary domain. Otherwise, the next step will fail.'),
				lang.replace(_('Download the {link} for Microsoft Powershell.'), {link: '<a href="/univention/command/office365/saml_setup.bat" target="_blank">' + _('SAML configuration script') + '</a>'}) + ' ' +
				_('Execute the downloaded SAML configuration script, and authenticate with the Azure Active Directory domain administrator account.') + this.img(_('saml_setup_script_windows_EN.png')),
				_('If the script has been executed successfully, single sign-on configuration is completed. Continue by clicking on <i>Next</i>.')
			]);
		},

		getTextUniventionConfigRegistry: function() {
			return this.formatParagraphs([
				_('For the UCS user account for which Office 365 is enabled, an account in the Microsoft directory is created and selected account attributes get synchronized from UCS to the Microsoft directory.'),
				_('Via the Univention Config Registry variable <i>office365/attributes/sync</i> can be configured which LDAP attributes (e.g. given name, surname, etc.) of a user account are sychronized.') + ' ' +
				_('You may add or remove attributes from the list by using the %s.', [tools.linkToModule({module: 'ucr'})]),
				_('Additional configuration settings can be viewed in the help of the UCR variables <i>office365/attributes/anonymize</i> and <i>office365/attributes/static/.*</i>.') + ' ' +
				_('You can enable the UCR variable <i>office365/groups/sync</i> to synchronize the groups of the enabled Office 365 users.')
			]);
		},

		getTextSuccessPage1: function() {
			return this.formatParagraphs([
				_('You can now enable the Microsoft Azure synchronization for users on the <i>Office 365</i> tab in the %s.', [tools.linkToModule({module: 'udm', flavor: 'users/user'})]),
				_('To learn more about configuring individual subscriptions and service plans for users, see <a href="%s" target="_blank">the Office 365 Connector documentation</a>', _('http://wiki.univention.de/index.php?title=Microsoft_Office_365_Connector')) + '<br>' + this.img(_('umc_office365_EN.png'))
			]);
		},

		formatParagraphs: function(data) {
			return '<p>' + data.join('</p><p>') + '</p>';
		},

		formatOrderedList: function(data, props) {
			var start = (props && props.start) ? 'start="' + props.start + '" ' : '';
			return '<ol ' + start + 'style="padding: 0; list-style-position: inside;"><li>' + data.join('</li><li>')  + '</li></ol>';
		},

		img: function(image) {
			return '<br/><img style="min-width: 250px; max-width: 100%; padding-left: 1em;" src="' + require.toUrl('umc/modules/office365/' + image) + '">';
		},

		initWizard: function(data) {
			array.forEach(['already-initialized', 'single-sign-on'], function(name) {
				this.getWidget('start', name).set('visible', data.result.initialized);
			}, this);
			tools.forIn(data.result, lang.hitch(this, function(key, val) {
				var widget = this.getWidget('add-application', key);
				if (widget) {
					widget.set('value', lang.replace(val, {origin: this.origin}));
				}
			}));
		},

		manifestUploaded: function(data) {
			this.authorizationurl = data.result.authorizationurl;
//			iframe("data:application/octet-stream;headers=Content-Disposition%3A%20attachment%3B%20filename%3Dmanifest.json;charset=utf-8;base64," + data.result.manifest);  // sucks...
//			domConstruct.create('a', {href: 'data:application/octet-stream;charset=utf-8;base64,' + data.result.manifest, 'download': 'manifest.json', style: 'display: none;', 'innerHTML': 'manifest.json'}, dojo.body()).click();  // IE11 sucks
			domConstruct.create('a', {target: '_blank', href: '/univention/command/office365/manifest.json', 'download': 'manifest.json', style: 'display: none;', 'innerHTML': 'manifest.json'}, dojo.body()).click();
			this._next('manifest-upload');
		},

		openAuthorization: function() {
			this.authorizationWindow = window.open(this.authorizationurl);
			if (!this.authorizationWindow) {  // pop up blocker
				dialog.alert(_('Could not open a new browser window. Please deactivate all pop up blocker for this site.'));
				return;
			}
			if (this._progressDeferred.isFulfilled()) {
				this.resetProgress();
				this.startPolling();
			}
			this.standbyDuring(this._progressDeferred, this._progressBar);
		},

		resetProgress: function() {
			if (this._progressDeferred && !this._progressDeferred.isFulfilled()) {
				this._progressDeferred.cancel();
			}
			this._progressBar = new ProgressBar();
			this._progressDeferred = new Deferred();
			this._progressBar.setInfo(null, null, Infinity);
			this._progressBar.feedFromDeferred(this._progressDeferred, _('Office 365 configuration'));
		},

		startPolling: function() {
			// start polling the state of the initialization. This is also important here to make sure no session timeout occurs.
			return this.umcpCommand('office365/state').then(lang.hitch(this, function(data) {
				var result = data.result || {};
				result.percentage = result.percentage || Infinity;
				this._progressDeferred.progress(result);
				if (result.finished) {
					this._progressDeferred.resolve(result);
					this._next('authorize');
					return;
				}
				if (result.waiting && this.authorizationWindow && this.authorizationWindow.closed) {
					this._progressDeferred.resolve(result);
					return;
				}
				if (!this._progressDeferred.isFulfilled()) {
					setTimeout(lang.hitch(this, 'startPolling'), 500);
				}
			}), lang.hitch(this, function(error) {
				this._progressDeferred.reject();
				this.switchPage('error');
			}));
		},

		next: function(pageName) {
			var nextPage = this.inherited(arguments);
			if (nextPage == 'authorize') {
				// when switching to the authorization page we need to make sure that the session is still active and keeps active until the authorization was done
				this.resetProgress();
				this.startPolling().then(function() {
					return nextPage;
				}, function() {
					return pageName;
				});
			} else if (nextPage == 'add-application') {
				if (window.location.protocol != 'https:') {
					dialog.alert(_('It is necessary to <a href="https://%(url)s">run this wizard while using the Univention Management Console with a https connection.</a> If you continue without a https connection, the wizard will likely not complete.', {
								url: window.location.href.slice(7)	
							}),
						_('Warning'));
				}
			}
			return nextPage;
		},

		getFooterButtons: function(pageName) {
			var buttons = this.inherited(arguments);
			if (pageName == "manifest-upload") {
				buttons = array.filter(buttons, function(button) { return button.name != 'next'; });
			}
			if (pageName == 'authorize') {
				buttons = array.filter(buttons, function(button) { return button.name != 'finish'; });
			}
			return buttons;
		},

		hasNext: function(pageName) {
			if (~array.indexOf(['authorize', "success3", 'error'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		hasPrevious: function(pageName) {
			if (~array.indexOf(["azure-integration", 'single-sign-on-setup', "success", 'error'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		canCancel: function(pageName) {
			if (~array.indexOf(["start", 'add-application', "ucs-integration", "manifest-upload", "success", "success2", 'success3', 'error'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		}
	});

	return declare("umc.modules.office365", [ Module ], {
		_wizard: null,

		unique: true,

		postMixInProperties: function() {
			this.inherited(arguments);
			this._wizard = new OfficeWizard({
				umcpCommand: lang.hitch(this, 'umcpCommand')
			});
			this.standbyDuring(this.umcpCommand('office365/query').then(lang.hitch(this._wizard, 'initWizard'), lang.hitch(this, 'closeModule')));
			this._wizard.on('finished', lang.hitch(this, 'closeModule'));
			this._wizard.on('cancel', lang.hitch(this, 'closeModule'));
			this.on('close', lang.hitch(this, function() {
				if (this._wizard._progressDeferred) {
					this._wizard._progressDeferred.reject();
				}
				if (this._wizard.authorizationWindow) {
					this._wizard.authorizationWindow.close();
				}
			}));
			this._wizard.set('headerButtons', [{
				name: 'help',
				iconClass: 'umcHelpIconWhite',
				label: _('Help'),
				callback: lang.hitch(this, function() {
					dialog.alert([
						_('This wizard helps you to configure the connection between UCS and Microsoft Office 365.'), '<br>',
						_('You need a <a href="%(domain)s" target="_blank">verified domain</a> and access to the <a href="%(dev)s" target="_blank">Microsoft Azure Portal</a> with a Microsoft Office 365 administrator account.', {
							domain: _('https://azure.microsoft.com/en-us/documentation/articles/active-directory-add-domain/'),
							dev: _('https://manage.windowsazure.com/')
						})
					].join(' '), _('Microsoft Office 365 setup wizard'));
				})
			}]);
		},

		buildRendering: function() {
			this.inherited(arguments);
			this.addChild(this._wizard);
		},

		postCreate: function() {
			this.inherited(arguments);
			aspect.after(this._wizard, 'switchPage', lang.hitch(this, function() {
				this._bottom.domNode.scrollTo(0, 0);
			}));
		}
	});
});
