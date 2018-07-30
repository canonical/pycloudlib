#!/usr/bin/env python3
"""Python packaging configuration."""
import os
from setuptools import find_packages, setup

PWD = os.path.abspath(os.path.dirname(__name__))
REQUIREMENTS_FILE = os.path.join(PWD, 'requirements.txt')
REQUIREMENTS = []
with open(REQUIREMENTS_FILE, 'r') as req_file:
    REQUIREMENTS = req_file.read().splitlines()

README_FILE = os.path.join(PWD, 'README.md')
with open(README_FILE, 'r') as readme:
    README_TEXT = readme.read()

setup(
    name='pycloudlib',
    version='18.3.1',
    description=(
        'Python library to launch, interact, and snapshot cloud instances'
    ),
    long_description=README_TEXT,
    long_description_content_type='text/markdown',
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
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ]
)
