# Test

This project contains _unittests_ that check that each class has the expected behavior and _integration test_ that check 
that the package and UCS system are connected the right way with Azure Active Directory.

Both tests (_unit_ and _integration_) require the prior configuration of at least two accounts in Azure (_ec2_ folder).
Usually, this process is manual for the administrator through a Wizard in UMC.

In the case of the automatic tests, a way to avoid this manual process was sought at the time. The solution consists of saving, 
compressing, and restoring for each test the information related to the Azure accounts created for testing and located in 
/etc/univention-office365/.

In the development process, when manual tests are executed, to avoid having to go through all the Wizard over and over again 
to get these accounts configured, this directory is also used.

That directory is so called "ec2". The information it contains gives access to the testing accounts
created by Univention in Azure.

You can locate the needed files in this folder in the jenkins server:
```shell
scp -r -C <user>@jenkins:/var/lib/jenkins/ec2/ .
```

If you don't have access to this server with your credentials you would need to ask for help in the [#dist](https://chat.univention.de/channel/dist) channel.

## Unittest

Unittest check all methods of each class and detect if any method (possibly any new one) isn't tested. (**_test_completity_**)

### Where can you find them?

Unittest are located in [test](/test).

### How to run

To run unittest you need have installed the following packages for test in python3:
  - python3-pytest
  - python3-mock
  - python3-requests-mock
  - python3-attr
  - python3-vcr
  - python3-six
  - python3-jwt
  - python3-rsa
  - python3-retrying
  - python3-redis

Also, you need to set the `ec2` path on `DOMAIN_PATH` in the file [test/__init__.py](/doc_improve/test/__init__.py).

Execute the following command:

```shell
cd <project_path>
pytest-3
```

## Integration test

Integration test check that the Office connector has the expected behavior.

### Where can you find them?

Integration test are located in [92_office365](/92_office365) and the package that contain it is `ucs-test-office365`.

If you want more details on what each test does, you can read the description contained in each file.

### How to run

These tests can be executed in 2 ways: manually in one VM or with a Jenkins Job.

#### On a Virtual Machine

In this case you need to install office365 connector in a UCS system and copy `ec2` to `/etc/univention-office365`.

Then you need to install the package `ucs-test-office365`.

And finally, you can run:

```shell
ucs-test -s office365 -E dangerous
# or 
ucs-test -s office365 -E dangerous -l test.log -F raw
```


#### In Jenkins

To run this test in Jenkins you need to update the packages in the [App Provider Portal](https://provider-portal.software-univention.de/univention/management/#module=appcenter-selfservice::0:).  

Then we go to [Jenkins](https://jenkins.knut.univention.de:8181/) and open _UCS-{version}_>_UCS-{version}-{patch}_>_Product Test_>_Component office365_>_Build with Parameters_

To run the integration test for the app, set the configuration variables to choose the right version that you want to test and press on `Execute` button.

Usually when running the test while developing, you would want the packages of `appcenter-test` to be used. To get it done
you can use these parameters as a reference:
```
COMPONENT_VERSION: testing
release_update: public
errata_update: public
```

