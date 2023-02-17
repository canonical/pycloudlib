#!/usr/bin/env python3
"""Python packaging configuration."""
import os
from pathlib import Path

from setuptools import find_packages, setup


def read_readme():
    """Read and return text of README.md."""
    pwd = os.path.abspath(os.path.dirname(__name__))
    readme_file = os.path.join(pwd, "README.md")
    with open(readme_file, "r", encoding="utf-8") as readme:
        readme_txt = readme.read()

    return readme_txt


def read_version():
    """Read and return text of VERSION."""
    return (
        Path(__file__)
        .parent.joinpath("VERSION")
        .read_text(encoding="utf-8")
        .strip()
    )


INSTALL_REQUIRES = [
    "azure-cli-core >= 2.21.0",
    "azure-identity",
    "azure-mgmt-compute >= 17",
    "azure-mgmt-network >= 16",
    "azure-mgmt-resource >= 15",
    "boto3 >= 1.14.20",
    "botocore >= 1.17.20",
    "google-api-python-client >= 1.7.7",
    "ibm-platform-services",
    "knack >= 0.7.1",
    "oci >= 2.17.0",
    "paramiko >= 2.9.2",
    "protobuf < 3.20.0",
    "pyparsing >= 2, < 3.0.0",
    "python-openstackclient >= 5.2.1",
    "pyyaml >= 5.1",
    "requests >= 2.22",
    "toml == 0.10",
    "python-simplestreams == 0.1.0.post19",
]

EXTRAS_REQUIRE = {
    ":python_version == '3.6'": [
        "ibm-cloud-sdk-core == 3.14.0",  # last py36 compatible version
        "ibm-vpc == 0.10",
    ],
    ":python_version >= '3.7'": [
        "ibm-cloud-sdk-core >= 3.14.0",
        "ibm-vpc >= 0.10",
    ],
}

setup(
    name="pycloudlib",
    version=read_version(),
    description=(
        "Python library to launch, interact, and snapshot cloud instances"
    ),
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="pycloudlib-devs",
    author_email="pycloudlib-devs@lists.launchpad.net",
    url="https://launchpad.net/pycloudlib",
    license="GNU General Public License v3 (GPLv3)",
    packages=find_packages(),
    python_requires=">=3.6",
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    zip_safe=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
)
