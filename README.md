# pycloudlib

Python library to launch cloud instances and customize cloud images

## Install

Install directly from [PyPI](https://pypi.org/project/pycloudlib/):

```shell
pip3 install pycloudlib
```

Project's requirements.txt file can include pycloudlib as a dependency. Check out the [pip documentation](https://pip.readthedocs.io/en/1.1/requirements.html) for instructions on how to include a particular version or git hash.

Install from latest master:

```shell
git clone https://git.launchpad.net/pycloudlib
cd pycloudlib
python3 setup.py install
```

## Usage

The library exports each cloud wiht a standard set of functions for operating on instances, snapshots, and images. There are also cloud specific operations that allow additional operations.

## Bugs & Contact

File bugs on Launchpad at the [pycloudlib project](https://bugs.launchpad.net/pycloudlib/+filebug). To contact the developers use the pycloudlib-devs@lists.launchpad.net list.

## Hacking

1. Create a branch
    - `git clone https://git.launchpad.net/pycloudlib`
    - `cd pycloudlib`
    - `git remote add LP_USER ssh://LP_USER@git.launchpad.net/~LP_USER/pycloudlib`
    - `git push LP_USER master`
    - `git checkout -b YOUR_BRANCH`
2. Make your proposed changes to the library
3. Test using tox.ini
    - `tox`
    - This will also be run during the merge request process
4. Submit your branch
    - `git push -u LP_USER YOUR_BRANCH`
5. Propose a merge
    - Navigate to https://code.launchpad.net/~LP_USER/pycloudlib
    - Click on your branch and choose 'Propose for merging'
    - Target branch: set to 'master'
    - Enter a commit message
6. Review
    - Your branch will get auto-reviewed by a bot
    - Someone will come by and review your branch

### Style

Use [Google styling](https://github.com/google/styleguide/blob/gh-pages/pyguide.md) for docstrings.
