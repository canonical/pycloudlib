#!/usr/bin/env python3
"""Python packaging configuration."""
import os
from setuptools import find_packages, setup


def read_readme():
    """Read and return text of README.md."""
    pwd = os.path.abspath(os.path.dirname(__name__))
    readme_file = os.path.join(pwd, 'README.md')
    with open(readme_file, 'r') as readme:
        readme_txt = readme.read()

    return readme_txt


PKGS = open('requirements.txt', 'r').readlines()

setup(
    name='pycloudlib',
    version='18.8',
    description=(
        'Python library to launch, interact, and snapshot cloud instances'
    ),
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    author='pycloudlib-devs',
    author_email='pycloudlib-devs@lists.launchpad.net',
    url='https://launchpad.net/pycloudlib',
    license='GNU General Public License v3 (GPLv3)',
    packages=find_packages(),
    python_requires='>=3.4',
    install_requires=PKGS,
    zip_safe=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ]
)
