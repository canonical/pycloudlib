# pycloudlib

[![CI](https://github.com/canonical/pycloudlib/actions/workflows/ci.yaml/badge.svg)](https://github.com/canonical/pycloudlib/actions/workflows/ci.yaml)

Python library to launch, interact, and snapshot cloud instances

## Install

Install directly from [PyPI](https://pypi.org/project/pycloudlib/):

```shell
pip install pycloudlib
```

Install from the latest `main` branch:

```shell
git clone https://git.launchpad.net/pycloudlib
cd pycloudlib
uv sync
```

## Usage

The library exports each cloud with a standard set of functions for operating on instances, snapshots, and images. There are also cloud specific operations that allow additional operations.

See the examples directory or the [online documentation](https://pycloudlib.readthedocs.io/) for more information.

## Bugs

If you spot a problem, search if an issue already exists. If a related issue doesn't exist, open a
[new issue](https://github.com/canonical/pycloudlib/issues/new/choose).

## Contact

To contact the developers use the pycloudlib-devs@lists.launchpad.net list.
