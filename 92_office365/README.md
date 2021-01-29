

# How to start tests

In the current setup there is a dependency between the tests, because all tests
in this directory rely on the execution of `01_initialize_external_testenv`.

In order to execute any of the tests manually the
`01_initialize_external_testenv` has to be executed first and special care
must be taken for the correct system time, because the test requests a TOKEN
from microsoft, which is only valid for a certain time. But the script in its
current state always returns true. You are advised to execute `/etc/init.d/ntpd
restart` before executing it.

After that any of the other tests can be executed.

The `890_uninitialize_external_testenv` is theoretically there to clean up,
what `01_initialize_external_testenv` did before.
