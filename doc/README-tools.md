
- [Tools](#tools)
  * [Managing adconnections](#managing-adconnections)
    + [Create new adconnection](#create-new-adconnection)
    + [Remove adconnection](#remove-adconnection)
    + [List adconnections](#list-adconnections)
    + [Rename adconnections](#rename-adconnections)
  * [Managing users tokens](#managing-users-tokens)
  * [Clean Empty groups from azure](#clean-empty-groups-from-azure)
  * [List o365 users for all connections](#list-o365-users-for-all-connections)
  * [List user and groups](#list-user-and-groups)
  * [List o365 subscriptions](#list-o365-subscriptions)

<small><i><a href='http://ecotrust-canada.github.io/markdown-toc/'>Table of contents generated with markdown-toc</a></i></small>

---

# Tools
There are several useful scripts, they are located in `/usr/share/univention-office365/scripts/`

These scripts have like a goal help to administrator to admin connections, admin users tokens, 
clean empty groups and show some info about user, groups and subscriptions.
---
## Managing adconnections

You can manage adconnections whit this script (create, list, remove)
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

