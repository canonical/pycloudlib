Configuration
=============

Configuration is achieved via a configuration file. At the root of the pycloudlib repo is a file named *pycloudlib.toml.template*.
This file contains stubs for the credentials necessary to connect to any individual cloud. Fill in the details appropriately
and copy the file to either **~/.config/pycloudlib.toml** or **/etc/pycloudlib.toml**.

Additionally, the configuration file path can be passed to the API directly or via the **PYCLOUDLIB_CONFIG** environment variable.
The order pycloudlib searches for a configuration file is:

* Passed via the API
* PYCLOUDLIB_CONFIG
* ~/.config/pycloudlib.toml
* /etc/pycloudlib.toml


pycloudlib.toml.template
------------------------
.. literalinclude:: ../pycloudlib.toml.template
