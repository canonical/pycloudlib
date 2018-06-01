# This file is part of pycloudlib. See LICENSE file for license information.
"""Helpers for shell string and processing."""

import base64
from errno import ENOENT
import os
import shlex
import subprocess
import tempfile

from pycloudlib.exceptions import ProcessExecutionError


def chmod(path, mode):
    """Run chmod on a file or directory.

    Args:
        path: string of path to run on
        mode: int of mode to apply
    """
    real_mode = _safe_int(mode)
    if path and real_mode:
        os.chmod(path, real_mode)


def is_writable_dir(path):
    """Make sure dir is writable.

    Args:
        path: path to determine if writable

    Returns:
        boolean with result

    """
    try:
        touch(path)
        os.remove(tempfile.mkstemp(dir=os.path.abspath(path))[1])
    except (IOError, OSError):
        return False
    return True


def mkdtemp(prefix='pycloudlib'):
    """Make a temporary directory.

    Args:
        prefix: optional, temproary dir name prefix (default: pycloudlib)

    Returns:
        tempfile object that was created

    """
    return tempfile.mkdtemp(prefix=prefix)


def rmfile(path):
    """Delete a file.

    Args:
        path: run unlink on specific path
    """
    try:
        os.unlink(path)
    except OSError as error:
        if error.errno != ENOENT:
            raise error


def shell_pack(cmd):
    """Return a string that can shuffled through 'sh' and execute cmd.

    In Python subprocess terms:
        check_output(cmd) == check_output(shell_pack(cmd), shell=True)

    Args:
        cmd: list or string of command to pack up

    Returns:
        base64 encoded string

    """
    if isinstance(cmd, str):
        cmd = [cmd]
    else:
        cmd = list(cmd)

    stuffed = shell_safe(cmd)
    # for whatever reason b64encode returns bytes when it is clearly
    # representable as a string by nature of being base64 encoded.
    b64 = base64.b64encode(stuffed.encode()).decode()
    return 'eval set -- "$(echo %s | base64 --decode)" && exec "$@"' % b64


def shell_quote(cmd):
    """Quote a shell string.

    Args:
        cmd: command to quote

    Returns:
        quoted string

    """
    if isinstance(cmd, (tuple, list)):
        return ' '.join([shlex.quote(x) for x in cmd])

    return shlex.quote(cmd)


def shell_safe(cmd):
    """Produce string safe shell string.

    Create a string that can be passed to $(set -- <string>) to produce
    the same array that cmd represents.

    Internally we utilize 'getopt's ability/knowledge on how to quote
    strings to be safe for shell.  This implementation could be changed
    to be pure python.  It is just a matter of correctly escaping
    or quoting characters like: ' " ^ & $ ; ( ) ...

    Args:
        cmd: command as a list

    Returns:
        shell safe string

    """
    out = subprocess.check_output(
        ["getopt", "--shell", "sh", "--options", "", "--", "--"] + list(cmd))

    # out contains ' -- <data>\n'. drop the ' -- ' and the '\n'
    return out.decode()[4:-1]


def subp(args, data=None, rcs=None, env=None, shell=False):
    """Subprocess wrapper.

    Args:
        args: command to run
        data: data to pass
        rcs: array of valid return codes
        env: optional env to use
        shell: optional shell to use

    Returns:
        Tuple of out, err, return_code

    """
    rcs = [0] if not rcs else rcs

    devnull_fp = None
    # using devnull assures any reads get null, rather
    # than possibly waiting on input.
    if data is None:
        devnull_fp = open(os.devnull)
        stdin = devnull_fp
    else:
        stdin = subprocess.PIPE
        if not isinstance(data, bytes):
            data = data.encode()

    bytes_args = _convert_args(args)

    try:
        process = subprocess.Popen(
            bytes_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=stdin, env=env, shell=shell
        )
        (out, err) = process.communicate(data)
    except OSError as error:
        raise ProcessExecutionError(
            cmd=args, description=error, exit_code=error.errno,
            stdout="-", stderr="-"
        )
    finally:
        if devnull_fp:
            devnull_fp.close()

    # ensure blank instead of none.
    if not out:
        out = b''
    if not err:
        err = b''

    return_code = process.returncode
    if return_code not in rcs:
        raise ProcessExecutionError(
            cmd=args, stdout=out, stderr=err, exit_code=return_code
        )

    return out, err, return_code


def touch(path, mode=None):
    """Ensure a directory exists with a specific mode, it not create it.

    Args:
        path: path to directory to create
        mode: optional, mode to set directory to
    """
    if not os.path.isdir(path):
        with os.path.dirname(path):
            os.makedirs(path)
        chmod(path, mode)
    else:
        chmod(path, mode)


def _convert_args(args):
    """Convert subp arguments to bytes.

    Popen converts entries in the arguments array from non-bytes to bytes.
    When locale is unset it may use ascii for that encoding which can
    cause UnicodeDecodeErrors. (LP: #1751051)

    Args:
        args: string, bytes, or list of arguments to convert to bytes

    Returns:
        byte argument list

    """
    if isinstance(args, bytes):
        bytes_args = args
    elif isinstance(args, str):
        bytes_args = args.encode("utf-8")
    else:
        bytes_args = [
            x if isinstance(x, bytes) else x.encode("utf-8")
            for x in args
        ]

    return bytes_args


def _safe_int(possible_int):
    """Create an int as safely as possbile.

    Args:
        possible_int: variable to create into a integer

    Returns:
        integration or None

    """
    try:
        return int(possible_int)
    except (ValueError, TypeError):
        return None
