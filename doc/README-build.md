# Package Build

Currently, there is a Gitlab Pipeline to build packages when a commit is done on the main branches of the component. For more details you can look into
[./README-CI.md](README-CI.md)

In case these [pipelines](README-CI.md) do not work, the way to build the packages and import them into the UCS repository are:

* For version 4.4 packages SSH into `ssh <user>@dimma` server.
* For version 5.0 packages SSH into `ssh <user>@ladda` server.
* Uncomment/comment the UCS_VERSION variable in the next command lines:
```shell
#UCS_VERSION=5.0
UCS_VERSION=4.4

#Import source code
repo_admin.py -G git@git.knut.univention.de:univention/components/office365.git -p univention-office365 -b $UCS_VERSION -P . -s office365 -r $UCS_VERSION-0-0
#Build  
b$(echo $UCS_VERSION | tr -d '.')-scope office365 univention-office365
```
