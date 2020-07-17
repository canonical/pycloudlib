# This file is part of pycloudlib. See LICENSE file for license information.
"""Helpers for shell string and processing."""

import base64
import datetime
from errno import ENOENT
import platform
import os
import shlex
import subprocess
import tempfile

from pycloudlib.result import Result


UBUNTU_RELEASE_VERSION_MAP = {
    'focal': '20.04',
    'bionic': '18.04',
    'xenial': '16.04',
}


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


def subp(args, data=None, env=None, shell=False, rcs=(0,),
         shortcircuit_stdin=True):
    """Subprocess wrapper.

    Args:
        args: command to run
        data: data to pass
        env: optional env to use
        shell: optional shell to use
        rcs: tuple of successful exit codes, default: (0)
        shortcircuit_stdin: bind stdin to /dev/null if no data is given

    Returns:
        Tuple of out, err, return_code

    """
    devnull_fp = None

    if data is not None:
        stdin = subprocess.PIPE
        if not isinstance(data, bytes):
            data = data.encode()
    elif shortcircuit_stdin:
        # using devnull assures any reads get null, rather
        # than possibly waiting on input.
        devnull_fp = open(os.devnull)
        stdin = devnull_fp
    else:
        stdin = None

    bytes_args = _convert_args(args)

    try:
        process = subprocess.Popen(
            bytes_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=stdin, env=env, shell=shell
        )
        (out, err) = process.communicate(data)
    finally:
        if devnull_fp:
            devnull_fp.close()

    rc = process.returncode
    out = '' if not out else out.rstrip().decode("utf-8")
    err = '' if not err else err.rstrip().decode("utf-8")

    if rcs and rc not in rcs:
        if err:
            errmsg = err
        elif out:
            errmsg = out
        else:
            errmsg = "command failed silently"
        errmsg = "Failure (rc=%s): %s" % (rc, errmsg)
        raise RuntimeError(errmsg)

    return Result(out, err, rc)


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


def _get_local_ubuntu_arch():
    """Return the Ubuntu architecture suitable for the local system.

    This is not simply the local machine hardware name, as in some cases it
    differs from the Ubuntu architecture name. The most common case is x86_64
    hardware, for which the Ubuntu architecture name is 'amd64'. This function
    implements the required mapping.

    On Debian and Ubuntu systmes the full mapping between the GNU architecture
    names and the Ubuntu (Debian) architecture names is available in the
    '/usr/share/dpkg/cputable' file, however the GNU architecture names are
    again different from the machine hardware names from e.g. uname(1) or
    os.uname(). The full mapping is available in the 'config.guess' script from
    the GNU autotools, and it's complex. Let's keep it simple here, mapping
    only what is relevant for Ubuntu.
    """
    arch_map = dict(
        i686='i386',
        x86_64='amd64',
        aarch64='arm64',
        ppc='powerpc',
        ppc64el='ppc64el',
        ppcle='powerpcel'
    )

    local_arch = platform.machine()
    local_ubuntu_arch = arch_map.get(local_arch, local_arch)

    return local_ubuntu_arch


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


def get_timestamped_tag(tag):
    """Create tag with current timestamp.

    Args:
        tag: string, Base tag to be used

    Returns
        An updated tag with current timestamp

    """
    return'%s-%s' % (
        tag, datetime.datetime.now().strftime("%m%d-%H%M%S")
    )
