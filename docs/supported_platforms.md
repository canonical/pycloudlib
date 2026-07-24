# Supported platforms

This page documents the operating systems and Python versions that pycloudlib
is supported and tested on.

## Host operating system

pycloudlib runs on **Linux only**.

### Support matrix

The version of python supported will track the versions of python included in the [two most-recent Ubuntu LTS releases](https://ubuntu.com/about/release-cycle).

 The current Host Operating system and python support matrix represets the tested host environments:

| Host OS             | Native Python | CI runner        | Tox env  |
|---------------------|---------------|------------------|----------|
| Ubuntu 24.04 LTS    | 3.12          | `ubuntu-24.04`   | `py312`  |
| Ubuntu 26.04 LTS    | 3.14          | `ubuntu-26.04`*  | `py314`* |

### Notes

* Other Linux distributions *may* work but are not tested. Bugs reported
  against untested distributions will be considered on a best-effort basis.
* Windows and macOS are not supported.
* Integration tests have Linux-only hard requirements that prevent the host
  OS matrix from extending beyond Linux:
  * the **LXD snap** (installed via the `canonical/setup-lxd` action in
    `.github/workflows/ci.yaml`), and
  * the **`distro-info`** apt package.

## Python versions

pycloudlib's documented and tested minimum Python version is **3.12**, the
native Python of the oldest in-scope Ubuntu LTS release (24.04).
