"""Common GCE utils."""
from urllib.error import HTTPError


class GceException(Exception):
    """Represents an error from the GCE API."""


def raise_on_error(response):
    """Look for errors in response and raise if found."""
    if 'httpErrorStatusCode' in response:
        raise HTTPError(
            url=response['selfLink'],
            code=response['httpErrorStatusCode'],
            msg=response['httpErrorMessage'],
            hdrs={},
            fp=None
        )
    if 'error' in response:
        raise GceException(
            'Received error(s)!\n'
            'Errors: {}'.format(response['error']['errors'])
        )
