# Release History

## 18.6

- enable Python 3.4 and Python 4.5 support

## 18.5.3

- 37bb7d6 result: switch from UserString to str

## 18.5.2

- 17f1b36 result: add boolean and optional params

## 18.5.1

- b6b14d0 result: add __repr__
- 2618925 docs: add result and renamed files

## 18.5

- c753e27 result: bug fixes of new usage
- 9de5a25 result: add execution result object
- 2a60386 cloud and instance: give each a type
- 59b68c5 base: rename base_cloud and base_instance
- 8a099d5 logging: set NullHandler by default
- 00fb428 tag: move tagging to base cloud
- 4de207a exceptions: removes custom exceptions from codebase
- b958f75 ec2: lower log evel of hot-add EBS & ENI

## 18.4

- d7fa81b defaults: SSH Key and Image Release

## 18.3.1

- ebd88cb ec2: fix reboot

## 18.3

- 785cd1f cleanup: clean up API and examples

## 18.2

- 991897b ec2 example: choose more common instance type
- cf2df7b lxd: Add LXD support, docs, and examples
- 0b35aab ec2: fix shutdown -> stop
- df1f285 docs: Add code examples to docs and design doc

## 18.1.5

- 27296db ec2: change shutdown to stop

## 18.1.4

- d4414d8 log: add additional logging messages
- 6215f88 ec2: obtain pre-existing instance by id
- b9ca05d ec2: add user-data to launch method
- 2b58e9a examples: provide complete working EC2 example
- 48f30e6 docs: separate sections
- 19dc9b0 Makefile: add twine dependency when doing upload

## 18.1.3

- aec16a1 docs: Create custom EC2 documentation
- ab02524 docs: fix inheritance setup and keep __init__
- dec2091 setup.py: add readme to long description
- a565f65 ec2: add AWS EC2 support and module docs
- 7962620 setup.py: change trove classifiers to array
- 477f5bd Initial add of project files
