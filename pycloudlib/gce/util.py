"""Common GCE utils."""
import os
from urllib.error import HTTPError

import google.auth
from google.oauth2 import service_account

from pycloudlib.gce.errors import GceException


def raise_on_error(response):
    """Look for errors in response and raise if found."""
    if "httpErrorStatusCode" in response:
        raise HTTPError(
            url=response["selfLink"],
            code=response["httpErrorStatusCode"],
            msg=response["httpErrorMessage"],
            hdrs={},
            fp=None,
        )
    if "error" in response:
        raise GceException(
            "Received error(s)!\n"
            "Errors: {}".format(response["error"]["errors"])
        )


def get_credentials(credentials_path):
    """Get GCE account credentials.

    Try service account credentials first. If those fail, try the environment
    """
    credentials_path = os.path.expandvars(os.path.expanduser(credentials_path))
    if credentials_path:
        try:
            return service_account.Credentials.from_service_account_file(
                credentials_path
            )
        except ValueError:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    return google.auth.default()[0]
