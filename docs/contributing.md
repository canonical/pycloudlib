# Contributing

This document describes how to contribute changes to pycloudlib.

## Get the Source

The following demonstrates how to obtain the source from Launchpad and how to create a branch to hack on.

It is assumed you have a [Launchpad](https://launchpad.net/) account and refers to your launchpad user as LP_USER throughout.

```shell
git clone https://git.launchpad.net/pycloudlib
cd pycloudlib
git remote add LP_USER ssh://LP_USER@git.launchpad.net/~LP_USER/pycloudlib
git push LP_USER master
git checkout -b YOUR_BRANCH
```

## Make Changes

### Development Environment

The makefile can be used to create a Python virtual environment and do local testing:

```shell
# Creates a python virtual environment with all requirements
make venv
. venv/bin/activate
```

### Documentation

The docs directory has its own makefile that can be used to install the dependencies required for document generation.

Documentation should be written in Markdown whenever possible.

### Considerations

When making changes please keep the following in mind:

* Keep pull requests limited to a single issue
* Code must be formatted to [Black](https://black.readthedocs.io/en/stable/index.html) standards
  * Run `tox -e format` to reformat code accordingly
* Run `tox` to execute style and lint checks
* When adding new clouds please add detailed documentation under the `docs` directory and code examples under `examples`

## Submit a Merge Request

To submit your merge request first push your branch:

```shell
git push -u LP_USER YOUR_BRANCH
```

Then navigate to your personal Launchpad code page:

https://code.launchpad.net/~LP_USER/pycloudlib

And do the following:

* Click on your branch and choose 'Propose for merging'
* Target branch: set to 'master'
* Enter a commit message formatted as follows:

```text
topic: short description

Detailed paragraph with change information goes here. Describe why the
changes are getting made, not what as that is obvious.

Fixes LP: #1234567
```

The submitted branch will get auto-reviewed by a bot and then a developer in the [pycloudlib-devs](https://launchpad.net/~pycloudlib-devs) group will review of your submitted merge.

## Do a Review

Pull the code into a local branch:

```shell
git checkout -b <branch-name> <LP_USER>
git pull https://git.launchpad.net/<LP_USER>/pycodestyle.git merge_request
```

Merge, re-test, and push:

```shell
git checkout master
git merge <branch-name>
tox
git push origin master
```
