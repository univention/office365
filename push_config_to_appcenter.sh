#!/bin/bash

# Copyright 2025 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.

# Abort on nonzero exitstatus [-e]
set -o errexit
# Don't hide errors within pipes
set -o pipefail

APP_ID="office365"
UCS_VERSION="5.0"
download_univention-appcenter-control() {
  if ! [[ -x univention-appcenter-control ]]; then
    curl -s -o univention-appcenter-control https://provider-portal.software-univention.de/appcenter-selfservice/univention-appcenter-control
    chmod +x univention-appcenter-control
  fi
}

APP_VERSION="$(grep ^Version app/office365.ini | awk '{ print $3 }')"
APP_VERSION_STRING="${UCS_VERSION}/${APP_ID}=${APP_VERSION}"
echo "App version in source code is: '${APP_VERSION}'."
echo "The app version string used for the upload is '${APP_VERSION_STRING}'."

if ! [[ -e "${HOME}/.univention-appcenter-user" ]] || ! [[ -e "${HOME}/.univention-appcenter-pwd" ]]; then
  echo -e "\nTo upload the files to the test appcenter you will now be asked for your"
  echo "username and password. Hint: create ~/.univention-appcenter-user and"
  echo "~/.univention-appcenter-pwd to skip the question."
fi

# upload to univention app provider portal
download_univention-appcenter-control

if [[ -d app/packages ]]; then
  echo -e "\nRemoving old release directory."
  rm -rf app/packages
fi

mkdir app/packages
scp -r omar:/var/univention/buildsystem2/apt/ucs_${UCS_VERSION}-0-office365/all/*.deb app/packages/

echo -e "\nFiles to upload:\n-------------------------------------------------------------------------------"
find app/ -type f | sort


read -n1 -r -p "Press any key to continue or Ctrl-C to abort."
echo


./univention-appcenter-control upload "${APP_VERSION_STRING}" $(find app/ -type f | sort)

rm -rf app/packages
