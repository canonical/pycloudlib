#!/usr/bin/env python3
"""Python packaging configuration."""
import os
from setuptools import setup, find_packages

PWD = os.path.abspath(os.path.dirname(__name__))

REQUIREMENTS_FILE = os.path.join(PWD, 'requirements.txt')
REQUIREMENTS = []
with open(REQUIREMENTS_FILE, 'r') as req_file:
    REQUIREMENTS = req_file.read().splitlines()

setup(
    name='pycloudlib',
    version='0.1',
    description=('Python library to launch cloud instances and '
                 'customize cloud images'),
    author='pycloudlib-devs',
    author_email='pycloudlib-devs@lists.launchpad.net',
    url='https://launchpad.net/pycloudlib',
    license='GNU General Public License v3 (GPLv3)',
    packages=['pycloudlib'],
    install_requires=REQUIREMENTS,
    zip_safe=True,
    classifiers=[
        'Development Status :: 1 - Planning',
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
