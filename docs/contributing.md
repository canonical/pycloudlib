# Contributing

This document describes how to contribute changes to pycloudlib.

## Get the Source

The following demonstrates how to obtain the source from GitHub and how to create a branch to hack on.

It is assumed you have a [GitHub](https://github.com/) account. Fork the repository at
https://github.com/canonical/pycloudlib and replace `GH_USER` below with your GitHub username.

```shell
git clone https://github.com/GH_USER/pycloudlib
cd pycloudlib
git remote add upstream https://github.com/canonical/pycloudlib
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

## Submit a Pull Request

To submit your pull request first push your branch to your fork:

```shell
git push -u origin YOUR_BRANCH
```

Then navigate to https://github.com/canonical/pycloudlib and open a pull request from your branch.

Use a commit message formatted as follows:

```text
topic: short description

Detailed paragraph with change information goes here. Describe why the
changes are getting made, not what as that is obvious.

Fixes: #1234
```

A developer from the [pycloudlib-devs](https://github.com/orgs/canonical/teams/pycloudlib-devs) team will review your pull request.

## Do a Review

Pull the contributor's branch into a local branch:

```shell
git fetch upstream pull/PR_NUMBER/head:review-branch
git checkout review-branch
```

Test and, once approved, the maintainer will merge via GitHub.
