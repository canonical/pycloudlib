"""Utilities for use with QEMU."""

import errno
import socket

from pycloudlib.errors import CloudSetupError

next_port = 18000


def get_free_port():
    """Look for a free local port for SSHing to VM."""
    global next_port  # pylint: disable=global-statement
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        for port in range(next_port, next_port + 100):
            try:
                s.bind(("127.0.0.1", port))
                next_port = port + 1
                return str(port)
            except socket.error as e:
                if e.errno == errno.EADDRINUSE:
                    continue
                raise
        raise CloudSetupError(
            f"Could not find open port in {next_port}-{next_port + 100} range"
        )
    finally:
        s.close()
