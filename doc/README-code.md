# Code Structure and Documentation

## Modules

The code for this connector is organized into a module called office365 inside the main univention python module.  
Al the code and classes have being designed trying to clearly separate the functionality of code related
with UCS and UDM and on the other hand the functionality related with the connection to the Microsoft Graph API.

In the middle a connector classes are being used to connect to the Microsoft Graph API and to the UCS LDAP side.
Only this classes have the needed "knowledge" to connect both sides.

### Microsoft

While developing this wrapper around the Microsoft Graph API the thinking of keeping it as
independent as possible from the UCS LDAP side was taken into account. This way the `univention.office365.microsoft`
module could be used as an independent module to operate over the Microsoft Graph API.

#### Core
All the direct interaction with the Microsoft Graph API is being done in the `univention.office365.microsoft.core` module. 
The core also contains the logic to take care of the responses in a low level way, letting the classes in the Azure Objects
to take care of the behavior on a higher level.
The URIs needed to connect to the API are detailed in the URLs module.


### Account
An account defines a connection to the Microsoft Graph API. The credentials are stored in files for each account.
The account is identified by an alias. Each account can contains a token which is used to connect to the Microsoft Graph API.

#### Objects
To keep an Object-Oriented approach the classes for the Microsoft Graph API are being organized into
classes representing the objects in the Microsoft Azure Directory service.
* UserAzure
* GroupAzure
* TeamAzure
* SubscriptionAzure

This classes contains the attributes and methods needed to interact with the Microsoft Graph API on a
higher level of abstraction.

### Async queue
Some Microsoft API calls are asynchronous. This means that the
call is made, but the response is not returned immediately.

A queue is used to store the `tasks` to be performed. The queue is
shared with another process that will consume the actions and would
execute them.

The queue can be implemented with several backends. The
default is a json file directory containing files for each task.
A Redis backend is also available as an example but not currently used.

The code related to the Async Queue is in `modules/univention/office365/asyncqueue.py`.

### UDM Wrapper
When the listener receives an event from the UCS LDAP side for an action, it receives
the dn of the object, the data of the object before the operation, the data of the object
after the operation and the action. This data of the old and the new object comes as a dictionary.
This dictionary of string keys and bytes values is the processed by the UDM wrapper to get
the representation of the object in a UDM class. The underlying LDAP reference is 
also kept as an attribute of the new UDM class.

This classes are a higher level abstraction of the objects in the LDAP layer.

* UDMOfficeUser
* UDMOfficeGroup

The functionality of this two objects have being extended to take care of the information related with the Microsoft connections/information
of each object.

### Connector
Until now only classes and methods to work with the data from the UCS/LDAP side and the Microsoft Azure Directory on the other side.

No logic have being described to connect the two sides until now.

This is the main function of the connector submodule. When the listener receives an action related with an object in the UCS LDAP side,
it's converted to the corresponding UDM Office object and then a specific connector is used
to replicate the operation on the Microsoft Azure Directory side.

Mainly two classes take care of the operations for the Users and Groups:
* UserConnector
* GroupConnector

Both classes have methods to create, delete and modify this objects. Also, several convenience methods
have being implemented in the connector to take care of some dependencies between these objects (pertences, memberships, ownership, etc).

### Utils
Several functions have being implemented to help with the development of the connector.

### UCR Helper
Univention Configuration Registry Helper. This class is used to get the configuration values from the UCR related to the office365 connector.
Convenience methods are being implemented to get and process the values from the UCR.
Any operation related to UCR for this connector should be implemented in this class.

### UDM Helper
Univention Directory Manager Helper. This class is used to get the UDM objects related to the office365 connector.
Convenience methods are being implemented to get and process the objects from UDM.
Any operation related to UDM for this connector should be implemented in this class.
