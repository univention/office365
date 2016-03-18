/*
 * Copyright 2016 Univention GmbH
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
/*global define,window*/

define([
	"dojo/_base/declare",
	"dojo/_base/lang",
	"dojo/_base/array",
	"dojo/Deferred",
	"umc/dialog",
	"umc/widgets/Module",
	"umc/widgets/Wizard",
	"umc/widgets/Text",
	"umc/widgets/TextBox",
	"umc/widgets/Uploader",
	"umc/widgets/ProgressBar",
	"umc/i18n!umc/modules/office365"
], function(declare, lang, array, Deferred, dialog, Module, Wizard, Text, TextBox, Uploader, ProgressBar, _) {
	var OfficeWizard = declare('umc.modules.office365.OfficeWizard', [Wizard], {

		_uploadDeferred: null,
		autoValidate: true,
		autoFocus: true,
		authorizationurl: null,

		constructor: function() {
			this.inherited(arguments);
			this.origin = window.location.protocol + '//' + window.location.host + (window.location.port ? ':' + window.location.port : '');
			this._moduleExists = new Deferred();
			this._progressBar = new ProgressBar();
			this._progressDeferred = new Deferred();

			lang.mixin(this, {
				pages: [{
					name: 'start',
					headerText: _('Microsoft Azure information'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'already-initialized',
						content: _('<b>Warning!</b> The current connection information will be replaced if the user continues.'),
						visible: false
					}, {
						type: Text,
						name: 'info',
						content: '<p>' + _('<b>Welcome to the Office 365 App configuration wizard.</b>') + '</p><p>' +
							_('Office 365 uses a directory in Microsofts cloud platform "Azure" to authenticate users.') + '</p><p>' +
							_('This app creates user accounts in the "Azure Active Directory" and connects them to UCS domain users. This allows them to use single sign-on to log into Office 365 Apps.') + '</p><p>' +
							_('To manage user accounts in the Azure AD, permissions must be granted by a Azure AD administrator. This wizard will guide you through the configuration process.') + '</p><p>' +
							_('To configure the connection to Azure, a working Microsoft Azure account is required.') + '</p><p>' +
							_('An Azure Active Directory with an Office 365 (test-)subscription has to be configured for your Azure account <i>before</i> continuing.') + '</p><p>' +
							_('The Azure Active Directory which is used to sync the users needs to have an active global administrator account which is used for login while configuring the Office365 App.') + '</p>'
					}]
				}, {
					name: 'add-external-application',
					headerText: _('Add external Application to Azure AD'),
					helpText: '',
					widgets: [{
						name: 'infos',
						type: Text,
						content: '<ol>' +
							'<li>' + _('Log into the <a href="https://manage.windowsazure.com/">Azure portal</a> and select your Active Directory. On the "Applications" tab, start the wizard to add a new application to your directory.') + '</li>' +
							'<li><img src="/univention-management-console/js/dijit/themes/umc/icons/screenshots/bottom_bar_add_app.png"></li>' +
							'<li>' + _('Choose the option that you want to create "an application my orgnaization is developing".') + '</li>' +
							'<li><img src="/univention-management-console/js/dijit/themes/umc/icons/screenshots/Azure_AD_App_wizard1.png"></li>' +
							'<li>' + _('Enter a Name for your application, e.g. <i>UCS Office 365</i>') + '</li>' +
							'<li>' + _('Select the <i>web-application and/or web-api</i> option and click Next') + '</li>' +
							'<li><img src="/univention-management-console/js/dijit/themes/umc/icons/screenshots/Azure_AD_App_wizard2.png"></li>' +
							'<li>' + _('Copy the following values and paster them into the respective fields in the Azure wizard:') + '<ul>' +
							'<li>' + _('SIGN-ON URL: {login-url}') + '</li>' +
							'<li>' + _('APP ID URI: {appid-url}') + '</li></ul></li>' +
							'<li><img src="/univention-management-console/js/dijit/themes/umc/icons/screenshots/Azure_AD_App_wizard3.png"></li>' +
//							'<li>' + _('Make sure that your browser can resolve {base-url}.') + '</li>' +
							'<li>' + _('Complete the <i>Add application</i> wizard in the Azure portal.') + '</li>' +
							'<li>' + _('Go to the next page of this wizard by clicking on Next.') + '</li></ol>'
					}]
				}, {
					name: 'ucs-integration',
					headerText: _('Integrate Azure connection into UCS'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: '<ol><li>' + _('When Azures <i>Add application</i> wizard completes, the new application should be selected.') + '</li><li>' +
							_('Click <i>Manage Manifest</i> and then <i>Download Manifest</i>. Save the manifest file on your computer.') + '</li><li>' +
							'TODO: make the step about "than one Active Directory" a separate page/popup' + '</li><li>' +
							_('Optionally paste the tenant ID if you have more than one Active Directory set up') + '</li><li>' +
							'<img src="/univention-management-console/js/dijit/themes/umc/icons/screenshots/bottom_bar_view_endpoints.png">' + '</li><li>' +
							'<img src="/univention-management-console/js/dijit/themes/umc/icons/screenshots/copy_tenant_id.png">' + '</li><li>' +
							'TODO: extract tenant_id from c&p URL' + '</li><li>' +
							_('UCS now has to modify the downloaded manifest file. Please upload the manifest by using the file upload option below') + '</li></ol>'
					}, {
						type: TextBox,
						name: 'tenant_id',
						label: _('Tenant Id'),
						value: 'common',
						onChange: lang.hitch(this, function(value) {
							this.getWidget('ucs-integration', 'upload').set('dynamicOptions', {
								tenant_id: value
							});
						})
					}, {
						type: Uploader,
						name: 'upload',
						buttonLabel: _('Upload manifest'),
						command: 'office365/upload',
						depends: 'tenant_id',
						dynamicOptions: {
							tenant_id: ''
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
					name: 'azure-integration',
					headerText: _('Make UCS office 365 app known to Azure AD - Upload manifest'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: '<p><a href=""><img src="js/umc/modules/download.svg" alt="Download manifest.json"></a></p>' +
							'<ol><li>' + _('To connect this Office365 App to your Microsoft Azure account, download the updated <a download="manifest.json" href="data:application/octet-stream;charset=utf-8;base64,{manifest}">manifest.json</a>') + '</li><li>' +
							_('Upload the manifest.json file via the Azure dashboard by selecting <i>manage manifest</i> and <i>upload manifest</i>') + //'</li><li>' +
//							_('Clicking on <i>next</i> causes a new window to open. There the connection between this app and Microsoft Azure has to be authorized.') +
							'</li></ol>'
					}]
				}, {
					name: 'azure-integration-auth',
					headerText: _('Make UCS office 365 app known to Azure AD - Authorize'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('To authorize the connection between this App and Microsoft Azure please follow these instructions:') +
							'<ol><li>' + //_('After the file was uploaded successfully, click <a href="{authorizationurl}" target="_blank">here</a> to authorize the connection between this App and Microsoft Azure.') + '</li><li>' +
							_('Authenticate on the Azure Webpage and complete the Authorization process by accepting the permission request.') + '</li><li>' +
							_('After accepting the permission request, the browser window or tab will close itself.') +// '</li><li>' +
//							_('Click on <i>finish</i> to test the configuration and end this wizard.') +
							'</li></ol>'
					}]
					buttons: [{
						name: 'authorize',
						label: _('Authorize app'),
						callback: lang.hitch(this, 'openAuthorization')
					}]
				}, {
					name: 'connectiontest',
					headerText: _('Connectiontest'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('Congratulations, the connection between UCS and Microsoft Azure has been established.') + ' ' +
							_('Users can now be synced to Microsoft Azure by activating the sync on the users <i>Office 365</i> tab.')
					}]

				}]
			});
		},

		initWizard: function(data) {
			this.getWidget('start', 'already-initialized').set('visible', data.result.initialized);
			var infos = this.getWidget('add-external-application', 'infos');
			infos.set('content', lang.replace(lang.replace(infos.get('content'), data.result), {origin: this.origin}));
		},

		manifestUploaded: function(data) {
			array.forEach(['azure-integration', 'azure-integration-auth'], function(pageName) {
				var infos = this.getWidget(pageName, 'infos');
				infos.set('content', lang.replace(infos.get('content'), data.result));
			}, this);
			this.authorizationurl = data.result.authorizationurl;

			// start polling for success in the background. This is important here to make sure no session timeout occurs.
			this._progressBar.auto('office365/test_configuration', {}, lang.hitch(this, function() {
				this._progressDeferred.resolve('connectiontest');  // switch to the last page
			}), undefined, undefined, undefined, this._moduleExists);

			this._next('ucs-integration');
		},

		openAuthorization: function() {
			this.authorizationWindow = window.open(this.authorizationurl);
//			if (!this.authorizationWindow) {
//				dialog.alert(this.authorizationurl);
//				return;
//			}
			setTimeout(lang.hitch(this, function() {
			
			}), 1000);
		},

		next: function(pageName) {
			var nextPage = this.inherited(arguments);
			if (nextPage == 'azure-integration-auth') {
				//this.openAuthorization();
			} else if (nextPage == 'connectiontest') {
				if (!this.authorizationWindow.closed) {
					dialog.alert('Please first make sure you authorized the application.');
					return pageName;
				} // TODO: test if the request was successful
				return this._connectionTest();
			}
			return nextPage;
		},

		_connectionTest: function() {
			this._progressBar.setInfo(_('Office 365 configuration'), _('Waiting for configuration to be completed.'), Infinity);
			this.standbyDuring(this._progressDeferred, this._progressBar);
			return this._progressDeferred;
		},

		getFooterButtons: function(pageName) {
			var buttons = this.inherited(arguments);
		//	if (pageName == 'azure-integration-auth') {
		//		array.forEach(buttons, function(button) {
		//			if (button.name == 'next') {
		//				button.label = _('Finish');
		//			}
		//		});
		//	} else
			if (pageName == "ucs-integration") {
				buttons = array.filter(buttons, function(button) { return button.name != 'next'; });
			}
			return buttons;
		},

		hasNext: function(pageName) {
			if (~array.indexOf(["connectiontest"], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		hasPrevious: function(pageName) {
			if (~array.indexOf(["azure-integration", 'azure-integration-auth', "connectiontest"], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		canCancel: function(pageName) {
			if (~array.indexOf(["start", 'add-external-application', "ucs-integration", "connectiontest"], pageName)) {
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
			this.standbyDuring(this.umcpCommand('office365/query').then(lang.hitch(this._wizard, 'initWizard')));
			this._wizard.on('finished', lang.hitch(this, 'closeModule'));
			this._wizard.on('cancel', lang.hitch(this, 'closeModule'));
			this.on('close', lang.hitch(this, function() {
				this._wizard._moduleExists.resolve();
			}));

		},

		buildRendering: function() {
			this.inherited(arguments);
			this.addChild(this._wizard);
		}
	});
});
