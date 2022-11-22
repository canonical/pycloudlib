Design
******

The following outlines some key points from the design of the library:

Images
======

Instances are expected to use the latest daily image, unless another image is specifically requested.

cloud-init
----------

The images are expected to have cloud-init in them to properly start. When an instance is started or during launch, the instance is checked for the boot complete file that cloud-init produces.

Instances
=========

Instances shall use consistent operation schema across the clouds. For example:

* launch
* start
* shutdown
* restart

In addition interactions with the instance are covered by a standard set of commands:

* execute
* pull_file
* push_file
* console_log

Exceptions
==========

All exceptions from underlying libraries are passed directly through for the end-user. There are a large number of exceptions to catch and possibilities, not to mention that they can change over time. By not catching them it informs the user that issues are found with what they are doing instead of hiding it from them.

Logging
=======

Logging is set up using the standard logging module. It is up to the user to set up their logging configuration and set the appropriate level.

Logging for paramiko, used for SSH communication, is restricted to warning level and higher, otherwise the logging is far too verbose.

Python Support
==============

pycloudlib currently supports Python 3.6 and above.

pycloudlib minimum supported Python version will adhere to the Python version of the oldest
`Ubuntu Version with Standard Support <https://wiki.ubuntu.com/Releases>`_.
After that Ubuntu Version reaches the End of Standard Support, we will stop testing upstream
changes against the unsupported version of Python and may introduce breaking changes.
This policy may change as needed.

The following table lists the Python version supported in each Ubuntu LTS release with Standard Support:

============== ==============
Ubuntu Version Python version
============== ==============
18.04 LTS      3.6
20.04 LTS      3.8
22.04 LTS      3.10
============== ==============
