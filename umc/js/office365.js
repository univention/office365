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
/*global require,define,window,setTimeout*/

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
	"umc/i18n!umc/modules/office365",
	"xstyle/css!./office365.css"
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

			lang.mixin(this, {
				pages: [{
					name: 'start',
					headerText: _('Microsoft Azure information'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'already-initialized',
						content: _('<b>Warning!</b> The configuration has already been done. If you continue, the current connection information will be replaced.'),
						visible: false
					}, {
						type: Text,
						name: 'info',
						content: this.getTextWelcome()
					}]
				}, {
					name: 'add-external-application',
					headerText: _('Add an Application to Azure AD'),
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
					name: 'success',
					headerText: _('Setup successful'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('Congratulations, the connection between UCS and Microsoft Azure has been established.') + ' ' +
							_('Users can now be synced to Microsoft Azure by activating the sync on the users <i>Office 365</i> tab.') + this.img(_('umc_office365_EN.png'))
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

			tools.forIn(this._pages, function(name, page) {
				page.addChild(new Text({
					'class': 'umcPageIcon',
					region: 'nav'
				}));
			});
		},

		getTextWelcome: function() {
			return this.formatParagraphs([
				_('<b>Welcome to the Office 365 App configuration wizard.</b>'),
				_('Welcome to the <a href="https://products.office.com/" target="_blank">Microsoft Office 365</a> configuration wizard. It will guide you through the process of setting up automatic provisioning of Microsoft Office 365 accounts for your user accounts.'),
				_('To use this app you need a active Microsoft Office 365 admin account, a global administrator account in the corresponding Azure AD and a <a href="https://azure.microsoft.com/en-us/documentation/articles/active-directory-add-domain/" target="_blank">verified domain</a>.')
			]);
		},

		getTextConfiguration: function() {
			return _('Please login to the <a href="https://manage.windowsazure.com/" target="_blank">Azure portal</a>, select your Active Directory and follow these steps:') + this.formatOrderedList([
				_('On the <i>Applications</i> tab, start the wizard to add a new application to your directory.') + this.img('bottom_bar_add_app.png'),
				_('Choose the option that you want to <i>add an application my organization is developing</i>') + this.img('add_application.png'),
				_('Enter a name for your application, e.g. <i>UCS Office 365</i>'),
				_('Select the <i>WEB APPLICATION AND/OR WEB-API</i> option and click on the <i>Next</i> button in the Azures Add-Application wizard.'),
				_('Copy the values below and paste them into the respective fields in the Azure wizard') // + this.img('uri_input_fields.png')
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
			return _('Please upload the JSON file that was just downloaded (with a name similar to <i>7e428ea7-e7d8-4f0c-93ed-c8e74c4050c9.json</i>), using the button below. The wizard will then take you to the next page.');
		},

		getTextAzureIntegration: function() {
			return this.formatOrderedList([
				_('Please <a download="manifest.json" href="data:application/octet-stream;charset=utf-8;base64,{manifest}">click here</a> to download the manifest.json file. Store it on your computer, then upload it to Azure via the Azure dashboard by selecting <i>manage manifest</i> and <i>upload manifest</i>') + this.img('manage_manifest.png'),
				_('When presented with the <i>Upload Manifest</i> window click on <i>BROWSE FOR FILE...</i> and select the previously downloaded <i>manifest.json</i>.') + this.img('azure_upload_manifest_window.png'),
				_('Click here on <i>Next</i> when the upload has succeeded.')
			]);
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
			return '<br/><img style="min-width: 250px; max-width: 100%; padding-left: 1em;" src="' + require.toUrl('umc/modules/office365/' + image) + '">';
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
			domConstruct.create('a', {href: 'data:application/octet-stream;charset=utf-8;base64,' + data.result.manifest, 'download': 'manifest.json'}).click();
			var widget = this.getWidget('upload-manifest', 'azure-integration');
			widget.set('content', lang.replace(widget.get('content'), data.result));
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
					this._next('azure-integration-auth');
					return;
				}
				if (result.waiting && this.authorizationWindow && this.authorizationWindow.closed) {
					this._progressDeferred.resolve(result);
					return;
				}
				setTimeout(lang.hitch(this, 'startPolling'), 500);
			}), lang.hitch(this, function(error) {
				this._progressDeferred.reject();
				this._next('success');
			}));
		},

		next: function(pageName) {
			var nextPage = this.inherited(arguments);
			if (nextPage == 'azure-integration-auth') {
				// when switching to the authorization page we need to make sure that the session is still active and keeps active until the authorization was done
				this.resetProgress();
				this.startPolling().then(function() {
					return nextPage;
				}, function() {
					return pageName;
				});
			}
			return nextPage;
		},

		getFooterButtons: function(pageName) {
			var buttons = this.inherited(arguments);
			if (pageName == "manifest-upload") {
				buttons = array.filter(buttons, function(button) { return button.name != 'next'; });
			}
			if (pageName == 'azure-integration-auth') {
				buttons = array.filter(buttons, function(button) { return button.name != 'finish'; });
			}
			return buttons;
		},

		hasNext: function(pageName) {
			if (~array.indexOf(['azure-integration-auth', "success", 'error'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		hasPrevious: function(pageName) {
			if (~array.indexOf(["azure-integration", 'azure-integration-auth', "success", 'error'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		canCancel: function(pageName) {
			if (~array.indexOf(["start", 'add-external-application', "ucs-integration", "manifest-upload", "success", 'error'], pageName)) {
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
				if (this._wizard.authorizationWindow) {
					this._wizard.authorizationWindow.close();
				}
			}));

		},

		buildRendering: function() {
			this.inherited(arguments);
			this.addChild(this._wizard);
		}
	});
});
