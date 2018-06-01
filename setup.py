#!/usr/bin/env python3
"""Python packaging configuration."""
import os
from setuptools import find_packages, setup

PWD = os.path.abspath(os.path.dirname(__name__))
REQUIREMENTS_FILE = os.path.join(PWD, 'requirements.txt')
REQUIREMENTS = []
with open(REQUIREMENTS_FILE, 'r') as req_file:
    REQUIREMENTS = req_file.read().splitlines()

setup(
    name='pycloudlib',
    version='18.1',
    description=(
        'Python library to launch cloud instances and customize cloud images'
    ),
    author='pycloudlib-devs',
    author_email='pycloudlib-devs@lists.launchpad.net',
    url='https://launchpad.net/pycloudlib',
    license='GNU General Public License v3 (GPLv3)',
    packages=find_packages(),
    python_requires='>=3.6',
    install_requires=REQUIREMENTS,
    zip_safe=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ]
)
