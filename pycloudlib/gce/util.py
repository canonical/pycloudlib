"""Common GCE utils."""

import os

import google.auth
from google.api_core.exceptions import GoogleAPICallError
from google.api_core.extended_operation import ExtendedOperation
from google.oauth2 import service_account

from pycloudlib.gce.errors import GceException


def raise_on_error(response):
    """Look for errors in response and raise if found."""
    if isinstance(response, GoogleAPICallError):
        raise GceException(
            "Received error(s)!\n" "Errors: {}".format(response.error_message)
        )
    if isinstance(response, ExtendedOperation):
        if response.error_code != 0:
            raise GceException(
                "Received error(s)!\n" "Errors: {}".format(
                    response.error_message
                )
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
