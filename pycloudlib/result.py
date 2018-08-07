# This file is part of pycloudlib. See LICENSE file for license information.
"""Base Result Class."""

from collections import UserString


class Result(UserString):  # pylint: disable=too-many-ancestors
    """Result Class."""

    def __init__(self, stdout, stderr='', return_code=''):
        """Initialize class."""
        super().__init__(stdout)

        self.stderr = stderr
        self.return_code = return_code

    def __repr__(self):
        """Return stdout."""
        return self.data

    def __bool__(self):
        """Boolean behavior."""
        return self.ok

    @property
    def failed(self):
        """Return boolean if result was failure."""
        if self.return_code == 0:
            return False
        return True

    @property
    def ok(self):
        """Return boolean if result was failure."""
        if self.return_code == 0:
            return True
        return False
