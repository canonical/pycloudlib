"""Common GCE utils."""


def raise_on_error(response):
    """Look for errors in response and raise if found."""
    if 'httpErrorStatusCode' in response:
        raise Exception(
            'Received HTTP error!\n'
            'status: {}\n'
            'message: {}\n'.format(
                response['httpErrorStatusCode'],
                response['httpErrorMessage']
            )
        )
    if 'error' in response:
        raise Exception(
            'Received error(s)!\n'
            'Errors: {}'.format(response['error']['errors'])
        )
