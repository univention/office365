[[_TOC_]]

---

# Tools
There are several useful scripts, they are located in `/usr/share/univention-office365/scripts/`

These scripts have like a goal help to administrator to admin connections, admin users tokens, 
clean empty groups and show some info about user, groups and subscriptions.

## Managing adconnections

You can manage adconnections with this script (create, list, remove)
```shell
/usr/share/univention-office365/scripts/manage_adconnections
```
### Create new adconnection
```shell
/usr/share/univention-office365/scripts/manage_adconnections create alias=<alias_name> [--makedefault]
```

### Remove adconnection
```shell
/usr/share/univention-office365/scripts/manage_adconnections remove alias=<alias_name>
```

### List adconnections
```shell
/usr/share/univention-office365/scripts/manage_adconnections list
```
### Rename adconnections

This command is not implemented.

---

## Managing users tokens

You can invalidate the token for one or all users, using this script.
```shell
/usr/share/univention-office365/scripts/o365_usertokens
```
```shell
Usage: o365_usertokens [options]

Options:
  -h, --help            show this help message and exit
  -m, --modify          Modify users, default: dry-run
  -o ONEUSER, --onlyone=ONEUSER
                        option: uid; Only look at and modify one user (for
                        testing purposes)
  -n, --new-password    (Deprecate) Set a new random password for the Azure AD user
  -i, --invalidate-tokens
                        Invalidate login tokens, forcing reauthentication
  --max-modifications=MAX_MODIFICATIONS
                        Invalidate tokens for a maximum of X users (default:
                        1000, overwrite default with UCR
                        office365/tokens/max_modifications)
```

---

## Clean Empty groups from azure

You can list or delete/deactivate empty groups from azure using this script.

```shell
/usr/share/univention-office365/scripts/check_for_empty_groups
```

```shell
usage: check_for_empty_groups [-h] [-d] connection

List (delete) empty groups ...

positional arguments:
  connection    connection to use

optional arguments:
  -h, --help    show this help message and exit
  -d, --delete  delete empty groups
```

---

## List o365 users for all connections

You can list one or all users in azure active directory for all connections you can use this script
```shell
/usr/share/univention-office365/scripts/o365_list_users
```

```shell
Usage: o365_list_users [options]

Options:
  -h, --help            show this help message and exit
  -o ONEUSER, --onlyone=ONEUSER
                        option: uid; Only look at one user (for
                        testing purposes)
```

---

## List user and groups

You can list all user and groups existing in your system synced with specific connection.

```shell
/usr/share/univention-office365/scripts/print_users_and_groups
```

```shell
Usage: print_users_and_groups [Azure AD connection alias]
```

---

## List o365 subscriptions

You can list all azure subscriptions existing in specific connection.

```shell
/usr/share/univention-office365/scripts/print_subscriptions
```

```shell
Usage: print_subscriptions [Azure AD connection alias]
```


## Getting started with `terminaltest.py`

If calling terminaltest.py leads to an error like `Application with identifier
'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' was not found in the directory` that is
probably the case, because a wrong connection was automatically pre-selected.
Check which connections exist on your system and choose another, like so:

```
root@master:~/office365# ./terminaltest.py -a
[
    "o365domain",
    "u-azure-test-de",
    "defaultADconnection",
    "azuretestdomain",
    "o365-dev-univention-de"
]
root@master:~/office365# ./terminaltest.py -g azuretestdomain
DEBUG:office365:adconnection_alias='azuretestdomain'
DEBUG:office365:adconnection_alias='azuretestdomain'
INFO:office365:proxy settings: {}
INFO:office365:service_plan_names=['SHAREPOINTWAC', 'SHAREPOINTWAC_DEVELOPER', 'OFFICESUBSCRIPTION', 'OFFICEMOBILE_SUBSCRIPTION', 'SHAREPOINTWAC_EDU']
```