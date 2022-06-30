[[_TOC_]]

# Build

This section gives a brief overview on the packages in this project, 
as well as, how to build these packages on a virtual machine or on servers in the Univention infrastructure like _ladda_ and _dimma_.

## Packages

This project contains several packages, the main Python package, UMC extension package and test package:

* `univention-office365`: This package contains:
  * Scripts for installation and other tools.
  * Syntax, handler, hooks for the LDAP objects and attributes.
  * Listener for the user and groups objects.
  * Service to convert *Groups* to *Teams*.
* `python-office365`/`python3-office365`: These packages contain a python2.7 and python3 module respectively to synchronize users and groups to Azure AD.
* `univention-management-console-module-office365`: This package contains the `UMC` module to set up new Azure account. 
* `ucs-test-office365`: This package contains integration tests.

## On Virtual Machine

To build and install the packages in your virtual machine, you must follow the steps below:

```shell
# copy the project to your virtual machine with scp or devsync

# Only for UCS 4.4
ucr set repository/online/unmaintained=yes 

# Configure repository to use local folder
echo "deb [trusted=yes] file:///root ./" >> /etc/apt/sources.list

# Install dependencies
cd ~/office365/ 
apt -y build-dep .

# Build the packages
dpkg-buildpackage -b --no-sign
cd
dpkg-scanpackages ./ /dev/null > Packages 

# Install de packages
# 5.0
univention-install -y univention-office365 python3-univention-office365 univention-management-console-module-office365 ucs-test-office365
# 4.4
univention-install -y univention-office365 python-univention-office365 univention-management-console-module-office365 ucs-test-office365
```

## Gitlab build

This project has a configuration file for a Gitlab CI/CD pipeline to build packages, with two different behaviors: For main branch and for any other branch.

### Main branch (`5.0` or `4.4`)

When you make a commit to the main branches (`5.0` or `4.4`) the pipeline runs automatically.
It builds the packages, updates the scope and imports the repository. After that upload the packages to the [App Center through the App Provider Portal](https://provider-portal.software-univention.de/univention/login/?location=%2Funivention%2Fmanagement%).

For more details you can look into
[./README-CI.md](/doc/README-CI.md)

The pipelines are a work in progress and not every stage is being executed for each branch.
For the 4.4 branch only the `test` stage is executed ([bug](https://git.knut.univention.de/univention/ucs/-/issues/1189)). 
For the 5.0 branch only the `test` and `build` stages are executed ([bug](https://git.knut.univention.de/univention/dist/repo-ng/-/issues/135)).

In case these [pipelines](/doc/README-CI.md) do not work, the way to build the packages and import them into the UCS repository are:

* For version 4.4 packages SSH into `ssh <user>@dimma` server.
* For version 5.0 packages SSH into `ssh <user>@ladda` server.
* Uncomment the `UCS_VERSION` variable in the next command lines, it depends on the version that you want to build:

```shell
#UCS_VERSION=4.4
#UCS_VERSION=5.0

UCS_SCOPE=$(echo $UCS_VERSION | tr -d '.')

#Import source code, 
# if this step fail maybe the pipeline import it,
# in this case you should continue with the next command
repo_admin.py -G git@git.knut.univention.de:univention/components/office365.git -p univention-office365 -b $UCS_VERSION -P . -s office365 -r $UCS_VERSION-0-0
#Build  
b$UCS_SCOPE-scope office365 univention-office365
```

To retrieve the packages you can use the following commands:
```shell
# to retrieve of the 4.4 version
scp -r emartinena@omar:/var/univention/buildsystem2/apt/ucs_4.4-0-office365/all .
# to retrieve of the 5.0 version
scp -r emartinena@omar:/var/univention/buildsystem2/apt/ucs_5.0-0-office365/all .
```

### Other branches
When you make a commit to any feature branch the pipeline is executed automatically,
but it doesn't build the packages in the servers.

You can download the pipeline artifacts and them upload it to the [App Center through the App Provider Portal](https://provider-portal.software-univention.de/univention/login/?location=%2Funivention%2Fmanagement%).

For more details you can look into
[README-CI.md](/doc/README-CI.md)
