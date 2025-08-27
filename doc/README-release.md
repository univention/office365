# Release Office365

This document outlines the process for releasing the Office365 connector.

## Create new versions in the test appcenter

Since UCS 5.2 has been released this repo has 2 branches: one for UCS 5.0 and one for UCS 5.2.

For the release you need to create 3 new app versions in the test appcenter:
1. 5.0 './univention-appcenter-control new-version 5.0/office365=<latest_published_version> 5.0/office365=<new_version_for_5.0>'
2. 5.1 './univention-appcenter-control new-version 5.0/office365=<new_version_for_5.0> 5.1/office365=<new_version_for_5.0>'
3. 5.2 './univention-appcenter-control new-version 5.0/office365=<new_version_for_5.0> 5.2/office365=<new_version_for_5.2>'

Format of the new version:
 * `new_version_for_5.0` -> 5.x -> Eg. 5.13
 * `new_version_for_5.2` -> 6.y -> Eg. 6.4

**Important**: After creating the new versions you need to check that all of them have the same `component_id`

## Checklist of changes

* [ ] Update the `Version` field in [office365.ini](/app/office365.ini) with the new version
* [ ] New changelog entry if the packages content has changed
* [ ] New entry in [README_UPDATE_DE](/app/README_UPDATE_DE) and [README_UPDATE_EN](/app/README_UPDATE_EN)
* [ ] Update docs in the UCS repo if needed

## Push the changes to the test appcenter

* [ ] Checkout branch `5.0` or `5.2` and run `./push_config_to_appcenter.sh`
  * [ ] Confirm that the script will upload the correct files to the test appcenter  
* [ ] For `5.1` you need to download the `*.deb` files from the latest published version eg. [office365_20250411121705](https://appcenter.software-univention.de/univention-repository/5.1/maintained/component/office365_20250411121705/all/) and upload it to the `5.1` version manually via https://provider-portal.software-univention.de/

## Test the new versions

To test the new versions you can run the product tests in Jenkins.
* [ ] 5.0 https://jenkins2022.knut.univention.de/job/UCS-5.0/job/UCS-5.0-10/view/Product%20Tests/job/product-test-component-office365/
* [ ] 5.2 https://jenkins2022.knut.univention.de/job/UCS-5.2/job/UCS-5.2-1/view/Product%20Tests/job/product-test-component-office365/
* [ ] Update from 5.0 to 5.2 https://jenkins2022.knut.univention.de/job/UCS-5.2/job/Apps/job/office365/job/App%20Autotest%20MultiEnv%20Release%20Update/

## Release the new versions

### Lock the mirror
```bash
ssh omar
sudo bash
ucr set update/mirror/disabled="Contact <your_username>: Release Office365"
exit
```

### Copy app version from test appcenter to production appcenter

```bash
ssh omar
cd /var/univention/buildsystem2/mirror/appcenter
component_id=office365_20250411121705
./copy_from_appcenter.test.sh 5.0 $component_id
./copy_from_appcenter.test.sh 5.1 $component_id
./copy_from_appcenter.test.sh 5.2 $component_id
```

### Update the mirror

```bash
ssh omar
cd /var/univention/buildsystem2/mirror/appcenter
# Dry run of the update to check if there are no other changes
sudo update_mirror.sh --verbose --debug appcenter
# If everything looks good, run the update
sudo update_mirror.sh --verbose appcenter
```

### Unlock the mirror

```bash
ssh omar
sudo bash
ucr unset update/mirror/disabled
exit
```
