The [.gitlab-ci.yml](../.gitlab-ci.yml) implements four stages, of which only
the first two are available in user branches. The `Staging` and `Deploy` stage
is only available on the default branch.

```mermaid
stateDiagram-v2
    Test --> Build
    Build --> Staging
    Staging --> Deploy
```

# Test

This stage implements quick sanity checks on the commited code changes. It is
there to detect quality issues with the changes and provide a quick feedback
to the developer. These stage should not take longer than a few seconds to
execute.


# Build

This stage uses the infamous `dpkg-buildpackage` tool to create packages and
stores these as artifacts. These can be downloaded and installed on a UCS
system.


# Staging

The changes from the repository are copied over to the main server. This step
is usually referred to as `import` at Univention.


# Deploy

In this stage the package is build again, but this time it is deployed into
our testing repository. The testing repository can be used in UCS systems
from within the univention network (e.g. VPN) by adding it to the
`/etc/apt/sources.list`, like so:

    deb [trusted=yes] http://192.168.0.10/build2/ ucs_4.4-0-errata4.4-7/all/
    deb [trusted=yes] http://192.168.0.10/build2/ ucs_4.4-0-errata4.4-7/$(ARCH)/

Packages can be manually tested from there and can also be released. 
`release` stage may be a subject for a future development and is not there yet.


# Specialities

* If the commit message contains `skip-build`, the CI pipeline never reaches
  the staging and deploy stages.

* The `.gitlab.ci` file has to be adapted for every major branch. Special
  care must be taken for the `variables` sections with all the version numbers.

* The `$SSH_PRIVATE_KEY` variable in .gitlab.ci is not defined in the
  `variables:` section, but rather a [project specific setting in gitlab
  ](https://docs.gitlab.com/ee/ci/variables/#cicd-variable-types). 

# SSH_PRIVATE_KEY

* Settings -> CI/CD -> Variables: Type: File, Protected (make sure the main branch is a proteced branch)

# Workarounds

The `$SSH_PRIVATE_KEY` variable points to a file within the docker container
and this file is created by Gitlab. The contents of this file is configurable
under

```
stateDiagram-v2
    Settings --> CI/CD
    CI/CD --> Variables
```

and we are using `Type: File` for it. The problem is though, that while this
file gets truncated within the docker container by one byte, which cuts of
the last minus sign of the SSH key stored in there. This makes the SSH client
complain with the error message: `ssh unknown key format`.

A future proof solution is to append a newline after SSH key, because that will
still work, even when the bug is fixed in Gitlab.

# Decision making



## should repo_admin and build-package-ng run in individual stages?

:heavy_check_mark: Pro:

- resembles the manual workflow.
- shortens the log for each command.
- Either of these steps could fail. It is easier to see which one.
- do one thing and do it right.
- allows manual restarts of individual steps.

:x: Contra:

- the pipeline gets longer
- we see no use in it for possible future developments, that jobs could run in
  parallel in the staging or deploy stage.






