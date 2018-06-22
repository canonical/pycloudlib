# Design

The following outlines some key points from the design of the library:

## Images

Instances are expected to use the latest daily image, unless another image is specifically requested.

### cloud-init

The images are expected to have cloud-init in them to properly start. When an instance is started or during launch, the instance is checked for the boot complete file that cloud-init produces.

## Instances

Instances shall use consistent operation schema across the clouds. For example:

* launch
* start
* stop
* restart

In addition interactions with the instance are covered by a standard set of commands:

* execute
* pull_file
* push_file
* console_log

## Exceptions

All exceptions from underlying libraries are passed directly through for the end-user. There are a large number of exceptions to catch and possibilities, not to mention that they can change over time. By not catching them it informs the user that issues are found with what they are doing instead of hiding it from them.

## Logging

Logging is setup using the standard logging module. It is up to the user to setup their logging configuration and set the appropriate level.

Logging for paramiko, used for SSH communication, is restricted to warning level and higher, otherwise the logging is far too verbose.
