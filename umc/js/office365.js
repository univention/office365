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
	"dojo/dom-construct",
	"dojo/Deferred",
	"umc/tools",
	"umc/dialog",
	"umc/widgets/Module",
	"umc/widgets/Wizard",
	"umc/widgets/Text",
	"umc/widgets/TextBox",
	"umc/widgets/Uploader",
	"umc/widgets/ProgressBar",
	"umc/i18n!umc/modules/office365"
], function(declare, lang, array, domConstruct, Deferred, tools, dialog, Module, Wizard, Text, TextBox, Uploader, ProgressBar, _) {
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
						content: this.getTextWelcome()
					}]
				}, {
					name: 'add-external-application',
					headerText: _('Add external Application to Azure AD'),
					helpText: '',
					widgets: [{
						name: 'infos',
						type: Text,
						content: this.getTextConfiguration()
					}, {
						type: TextBox,
						name: 'login-url',
						sizeClass: 'Two',
						label: _('SIGN-ON URL')
					}, {
						type: TextBox,
						name: 'appid-url',
						sizeClass: 'Two',
						label: _('APP ID URI')
					}, {
						name: 'complete',
						type: Text,
						content: this.formatOrderedList([_('Complete the <i>Add application</i> wizard in the Azure portal.')], {start: 6})
					}]
				}, {
					name: 'ucs-integration',
					headerText: _('Integrate Azure connection into UCS'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextUCSIntegration()
					}, {
						type: TextBox,
						name: 'tenant_id',
						label: _('Federation metadata document'),
						sizeClass: 'Two',
						value: '',
						onChange: lang.hitch(this, function(value) {
							this.getWidget('manifest-upload', 'upload').set('dynamicOptions', {
								tenant_id: value
							});
						})
					}]
				}, {
					name: 'manifest-upload',
					headerText: _('Upload manifest to UCS'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextManifestUpload()
					}, {
						type: Uploader,
						name: 'upload',
						buttonLabel: _('Upload manifest'),
						command: 'office365/upload',
						dynamicOptions: {
							tenant_id: 'common'
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
//					}, {
					}]
				}, {
					name: 'upload-manifest',
					headerText: _('Upload manifest to Azure'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'azure-integration',
						content: this.getTextAzureIntegration()
					}]
				}, {
					name: 'azure-integration-auth',
					headerText: _('Make UCS office 365 app known to Azure AD - Authorize'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextAzureAuthorization()
					}],
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
		},

		getTextWelcome: function() {
			return this.formatParagraphs([
				_('<b>Welcome to the Office 365 App configuration wizard.</b>'),
				_('Office 365 uses a directory in Microsofts cloud platform "Azure" to authenticate users.'),
				_('This app creates user accounts in the "Azure Active Directory" and connects them to UCS domain users. This allows them to use single sign-on to log into Office 365 Apps.'),
				_('To manage user accounts in the Azure AD, permissions must be granted by a Azure AD administrator. This wizard will guide you through the configuration process.'),
				_('To configure the connection to Azure, a working Microsoft Azure account is required.'),
				_('An Azure Active Directory with an Office 365 (test-)subscription has to be configured for your Azure account <i>before</i> continuing.'),
				_('The Azure Active Directory which is used to sync the users needs to have an active global administrator account which is used for login while configuring the Office 365 app.')
			]);
		},

		getTextConfiguration: function() {
			return _('Please login to the <a href="https://manage.windowsazure.com/" target="_blank">Azure portal</a>, select your Active Directory and follow these steps:') + this.formatOrderedList([
				_('On the <i>Applications</i> tab, start the wizard to add a new application to your directory.') + this.img('bottom_bar_add_app.png'),
				_('Choose the option that you want to <i>add an application my organization is developing</i>') + this.img('add_application.png'),
				_('Enter a name for your application, e.g. <i>UCS Office 365</i>'),
				_('Select the <i>WEB APPLICATION AND/OR WEB-API</i> option and click <i>Next</i>'),
				_('Copy the values below and paste them into the respective fields in the Azure wizard'), // + this.img('uri_input_fields.png'),
			]);
		},

		getTextUCSIntegration: function() {
			return this.formatOrderedList([
				_('When Azures <i>Add application</i> wizard completes, open the new application by clicking on it.'),
				_('In the bottom bar, click <i>MANAGE MANIFEST</i> and then <i>Download Manifest</i>. Save the manifest file on your computer.') + this.img('manage_manifest.png'),
				_('Click <i>VIEW ENDPOINTS</i>, copy the value for <i>FEDERATION METADATA DOCUMENT</i> and insert it into the text box below.') + this.img('copy_tenant_id.png')
			]);
		},

		getTextManifestUpload: function() {
			return _('Please upload the manifest file using the upload button below. After uploading the manifest you will be offered to download a file <i>manifest.json</i>. Store this file on your computer.');
		},

		getTextAzureIntegration: function() {
			return _('Now upload the <a download="manifest.json" href="data:application/octet-stream;charset=utf-8;base64,{manifest}">manifest.json</a> file via the Azure dashboard by selecting <i>manage manifest</i> and <i>upload manifest</i>');
		},

		getTextAzureAuthorization: function() {
			return [_('To authorize the connection between UCS and Microsoft Azure please click the button below.'),
				_('This will open a new browser window where you can complete the Authorization process by accepting the permission request.'),
				_('After accepting the permission request, the browser window or tab will close itself and the connection will be tested.')
			].join(' ');
		},

		formatParagraphs: function(data) {
			return '<p>' + data.join('</p><p>') + '</p>';
		},

		formatOrderedList: function(data, props) {
			var start = (props && props.start) ? 'start="' + props.start + '" ' : '';
			return '<ol ' + start + 'style="padding: 0; list-style-position: inside;"><li>' + data.join('</li><li>')  + '</li></ol>';
		},

		img: function(image) {
			return '<br/><img style="min-width: 250px; max-width: 100%; padding-left: 1em; /*border: thin solid red;*/" src="' + require.toUrl('umc/modules/office365/' + image) + '">';
		},

		initWizard: function(data) {
			this.getWidget('start', 'already-initialized').set('visible', data.result.initialized);
			tools.forIn(data.result, lang.hitch(this, function(key, val) {
				var widget = this.getWidget('add-external-application', key);
				if (widget) {
					widget.set('value', lang.replace(val, {origin: this.origin}));
				}
			}));
		},

		manifestUploaded: function(data) {
			this.authorizationurl = data.result.authorizationurl;
//			iframe("data:application/octet-stream;headers=Content-Disposition%3A%20attachment%3B%20filename%3Dmanifest.json;charset=utf-8;base64," + data.result.manifest);
			domConstruct.create('a', {href: 'data:application/octet-stream;charset=utf-8;base64,'+ data.result.manifest, 'download': 'manifest.json'}).click();
			var widget = this.getWidget('upload-manifest', 'azure-integration');
			widget.set('content', lang.replace(widget.get('content'), data.result));

			// start polling for success in the background. This is important here to make sure no session timeout occurs.
			this._progressBar.auto('office365/test_configuration', {}, lang.hitch(this, function() {
				var nextPage = 'connectiontest';
				if (this._progressBar.getErrors().critical) {
					nextPage = 'error';
				}
				this._progressDeferred.resolve(nextPage);  // switch to the last page
				this._next(nextPage);
			}), undefined, undefined, undefined, this._moduleExists);

			this._next('manifest-upload');
		},

		openAuthorization: function() {
			this.authorizationWindow = window.open(this.authorizationurl);
		},

		_connectionTest: function() {
			this._progressBar.setInfo(_('Office 365 configuration'), _('Waiting for configuration to be completed.'), Infinity);
			this.standbyDuring(this._progressDeferred, this._progressBar);
			return this._progressDeferred;
		},

		next: function(pageName) {
			if (this._progressDeferred.isFulfilled()) {
				return this._progressDeferred;
			}
			var nextPage = this.inherited(arguments);
			if (nextPage == 'connectiontest') {
				if (!this.authorizationWindow.closed) {
					dialog.alert('Please first make sure you authorized the application.');
					return pageName;
				}
				return this._connectionTest();
			}
			return nextPage;
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
			if (pageName == "manifest-upload") {
				buttons = array.filter(buttons, function(button) { return button.name != 'next'; });
			}
			if (pageName == 'azure-integration-auth') {
				buttons = array.filter(buttons, function(button) { return button.name != 'finish'; });
			}
			return buttons;
		},

		hasNext: function(pageName) {
			if (~array.indexOf(['azure-integration-auth', "connectiontest", 'error'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		hasPrevious: function(pageName) {
			if (~array.indexOf(["azure-integration", 'azure-integration-auth', "connectiontest", 'error'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		canCancel: function(pageName) {
			if (~array.indexOf(["start", 'add-external-application', "ucs-integration", "manifest-upload", "connectiontest", 'error'], pageName)) {
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
