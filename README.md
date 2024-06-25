# pycloudlib

[![Build Status](https://travis-ci.com/canonical/pycloudlib.svg?branch=master)](https://travis-ci.com/canonical/pycloudlib)

Python library to launch, interact, and snapshot cloud instances

## Install

Install directly from [PyPI](https://pypi.org/project/pycloudlib/):

```shell
pip3 install pycloudlib
```

Project's requirements.txt file can include pycloudlib as a dependency. Check out the [pip documentation](https://pip.readthedocs.io/en/1.1/requirements.html) for instructions on how to include a particular version or git hash.

Install from latest changes in `main` branch:

```shell
git clone https://github.com/canonical/pycloudlib.git
cd pycloudlib
python3 setup.py install
```

## Usage

The library exports each cloud with a standard set of functions for operating on instances, snapshots, and images. There are also cloud specific operations that allow additional operations.

See the examples directory or the [online documentation](https://pycloudlib.readthedocs.io/) for more information.

## Bugs

If you spot a problem, search if an issue already exists. If a related issue doesn't exist, open a
[new issue](https://github.com/canonical/pycloudlib/issues/new/choose).

## Contact

To contact the developers use the pycloudlib-devs@lists.launchpad.net list.
