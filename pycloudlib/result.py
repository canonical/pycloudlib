# This file is part of pycloudlib. See LICENSE file for license information.
"""Base Result Class."""


class Result(str):  # pylint: disable=too-many-ancestors
    """Result Class."""

    def __init__(self, stdout, stderr="", return_code=0):
        """Initialize class."""
        super().__init__()

        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code

    def __new__(cls, stdout, stderr, return_code):
        """Create new class."""
        obj = str.__new__(cls, stdout)
        obj.stderr = stderr
        obj.return_code = return_code
        return obj

    def __bool__(self):
        """Boolean behavior."""
        return self.ok

    @property
    def failed(self):
        """Return boolean if result was failure."""
        return not self.ok

    @property
    def ok(self):
        """Return boolean if result was success."""
        if self.return_code == 0:
            return True
        return False
