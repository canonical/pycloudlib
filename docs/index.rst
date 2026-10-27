pycloudlib
==========

Python library to launch, interact, and snapshot cloud instances

*************
Documentation
*************

Use the links in the table of contents to find:

* Cloud specific guides and documentation
* API documentation
* How to contribute to the project

*******
Install
*******

Install directly from `PyPI <https://pypi.org/project/pycloudlib/>`_:

.. code-block:: shell

    uv pip install pycloudlib

Install from the latest ``main`` branch:

.. code-block:: shell

    git clone https://git.launchpad.net/pycloudlib
    cd pycloudlib
    uv sync

*****
Usage
*****

The library exports each cloud with a standard set of functions for operating
on instances, snapshots, and images. There are also cloud specific operations
that allow additional operations.

See the examples directory or the `online documentation <https://pycloudlib.readthedocs.io/>`_
for more information.

****
Bugs
****

File bugs on `GitHub <https://github.com/canonical/pycloudlib/issues>`_.

*******
Contact
*******

If you come up with any questions or are looking to contact developers please
use the pycloudlib-devs@lists.launchpad.net list.


.. toctree::
   :hidden:
   :glob:
   :caption: Clouds

   clouds/*

.. toctree::
   :hidden:
   :glob:
   :caption: Code Examples

   examples/*

.. toctree::
   :hidden:
   :glob:
   :caption: Other

   configuration
   ssh_keys
   images
   resource_cleanup

.. toctree::
   :hidden:
   :caption: External

   File a bug <https://github.com/canonical/pycloudlib/issues>
   PyPI <https://pypi.org/project/pycloudlib/>

.. toctree::
   :hidden:
   :caption: Developers

   contributing
   maintainer
   design
   api
