# This file is part of pycloudlib. See LICENSE file for license information.
"""Exceptions used throughout the library."""


class PlatformError(IOError):
    """Exception for errors related to platforms."""

    def __init__(self, operation, description='unexpected error in platform'):
        """Init error and parent error class.

        Args:
            operation: Action occuring that caused exception
            description: Description of operation

        Raises:
            IOError

        """
        message = '%s: %s' % (description, operation)
        IOError.__init__(self, message)


class ProcessExecutionError(IOError):
    """Generic process execution error class."""

    MESSAGE_TEMPLATE = (
        '%(description)s\n'
        'Command: %(cmd)s\n'
        'Exit code: %(exit_code)s\n'
        'Stdout: %(stdout)s\n'
        'Stderr: %(stderr)s'
    )

    def __init__(self, cmd='-', stdout='-', stderr='-', exit_code='-',
                 description='unexpected error while running command'):
        """Create process execution exception.

        Args:
            cmd: Command run
            stdout: Standard output
            stderr: Standard error
            exit_code: Exit code
            description: Description of command

        Raises:
            IOError

        """
        if isinstance(cmd, list):
            cmd = ' '.join(cmd)

        self.cmd = cmd
        self.stdout = self._indent_text(stdout)
        self.stderr = self._indent_text(stderr)
        self.exit_code = exit_code
        self.description = description

        message = self.MESSAGE_TEMPLATE % {
            'description': self.description,
            'cmd': self.cmd,
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
        }
        IOError.__init__(self, message)

    @staticmethod
    def _indent_text(text, indent_level=8):
        """Indent text on all but the first line.

        Args:
            text: string or bytes to indent
            indent_level: int, how far to indent

        Returns:
            indented string

        """
        carriage_return = '\n'
        indent = ' ' * indent_level
        # if input is bytes, return bytes
        if isinstance(text, (bytes, bytearray)):
            carriage_return = carriage_return.encode()
            indent = indent.encode()
        # remove any newlines at end of text first to prevent unneeded
        # blank line in output
        return text.rstrip(carriage_return).replace(
            carriage_return, carriage_return + indent)


class InTargetExecuteError(ProcessExecutionError):
    """Exception for errors occuring in targets."""


class SSHKeyExistsError(IOError):
    """Exception for trying to recreate an SSH key."""


class SSHEncryptedPrivateKeyError(IOError):
    """SSH Key is encrypted and cannot be used."""


class NoKeyPairConfiguredError(IOError):
    """No valid KeyPair was configured."""


class NullInstanceError(IOError):
    """Exception for accessing null instance."""
