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
	"umc/widgets/Module",
	"umc/widgets/Wizard",
	"umc/widgets/Text",
	"umc/widgets/Uploader",
	"umc/widgets/ProgressBar",
	"umc/i18n!umc/modules/office365"
], function(declare, lang, array, Deferred, Module, Wizard, Text, Uploader, ProgressBar, _) {
	var OfficeWizard = declare('umc.modules.office365.OfficeWizard', [Wizard], {

		_uploadDeferred: null,
		autoValidate: true,
		autoFocus: true,

		constructor: function() {
			this.inherited(arguments);
			this.origin = window.location.protocol + '//' + window.location.host + (window.location.port ? ':' + window.location.port : '');
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
						content: '<p>' + _('Microsoft Azure is a cloud computing platform and infrastructure.') + '</p><p>' +
							_('To configure the connection to Azure, a working Microsoft Azure account is required.') + '</p><p>' +
							_('An Azure Active Directory with an Office365 (test-)subscription has to be configured for your Azure account before continuing.') + '</p><p>' +
							_('The Active Directory which is used to sync the users needs to have an active global administrator account which is used for login while configuring the Office365 App. The first created Active Directory in the account will be used to connect to by the office 365 app.') + '</p>'
					}]
				}, {
					name: 'add-external-application',
					headerText: _('Add external Application to Azure AD'),
					helpText: '',
					widgets: [{
						name: 'infos',
						type: Text,
						content: '<ol>' +
							'<li>' + _('In your Azure accounts Active Directory configuration, start the wizard to add a new application to your directory') + '</li>' +
							'<li>' + _('Choose the option that you want to configure an application developed by your company') + '</li>' +
							'<li>' + _('Enter a Name for your application, e.g. <i>UCS Office 365</i>') + '</li>' +
							'<li>' + _('Select the <i>web-application and/or web-api</i> option and click Next') + '</li>' +
							'<li>' + _('Paste the following values into the respective fields in the Azure wizard:') + '<ul>' +
							'<li>' + _('SIGN-ON URL: {login-url}') + '</li>' +
							'<li>' + _('APP ID URI: {appid-url}') + '</li></ul></li>' +
//							'<li>' + _('Make sure that your browser can resolve {base-url}.') + '</li>' +
							'<li>' + _('In Azure dashboard: Complete the <i>Add application</i> wizard.') + '</li></ol>'
					}]
				}, {
					name: 'ucs-integration',
					headerText: _('Integrate Azure connection into UCS'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: '<ol><li>' + _('In Azure Dashboard, the new application should be selected. Click on configure.') + '</li><li>' +
							_('In Azure dashboard, click <i>manage manifest</i> and then <i>download manifest</i>') + '</li><li>' +
							_('Save the manifest file and upload it.') + '</li></ol>'
					}, {
						type: Uploader,
						name: 'upload',
						buttonLabel: _('Upload manifest'),
						command: 'office365/upload',
						dynamicOptions: {
							tenant_id: null
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
					headerText: _('Make UCS office 365 app known to Azure AD'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: '<ol><li>' + _('Download <a download="manifest.json" href="data:application/octet-stream;charset=utf-8;base64,{manifest}">manifest.json</a>') + '</li><li>' +
							_('Upload the manifest.json file in the Azure dashboard by selecting <i>manage manifest</i> and <i>upload manifest</i>') + '</li><li>' +
							_('After the file was uploaded successfully, click <a href="{authorizationurl}" target="_blank">here</a> to authorize the connection between this App and Microsoft Azure.') + '</li><li>' +
							_('Click on <i>finish</i> to test the configuration and end this wizard.') + '</li></ol>'
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
			var infos = this.getWidget('azure-integration', 'infos');
			infos.set('content', lang.replace(infos.get('content'), data.result));

			// start polling for success in the background. This is important here to make sure no session timeout occurs.
			this._progressBar.auto('office365/test_configuration', {}, lang.hitch(this, function() {
				this._progressDeferred.resolve('connectiontest');  // switch to the last page
			}));

			this._next('ucs-integration');
		},

		next: function(pageName) {
			var nextPage = this.inherited(arguments);
			if (nextPage == 'connectiontest') {
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
			if (pageName == 'azure-integration') {
				array.forEach(buttons, function(button) {
					if (button.name == 'next') {
						button.label = _('Finish');
					}
				});
			} else if (pageName == "ucs-integration") {
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
			if (~array.indexOf(["azure-integration", "connectiontest"], pageName)) {
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
		},

		buildRendering: function() {
			this.inherited(arguments);
			this.addChild(this._wizard);
		}
	});
});
