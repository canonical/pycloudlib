# This file is part of pycloudlib. See LICENSE file for license information.
"""Private utilities for IBM cloud."""
from functools import partial
from time import sleep
from typing import Callable, Iterator, Optional

from ibm_vpc import DetailedResponse

from pycloudlib.errors import PycloudlibTimeoutError
from pycloudlib.util import get_query_param

_IBMCallable = Callable[..., DetailedResponse]


def iter_pages(
    op: _IBMCallable, *, start: Optional[str] = None, **kwargs
) -> Iterator[DetailedResponse]:
    """Lazily iterate over a paginated endpoint."""
    op = partial(op, **kwargs)
    detailed_response: DetailedResponse = op(start=start)
    result = detailed_response.get_result()
    yield detailed_response

    while result.get("next") is not None:
        next_url = result["next"]["href"]
        next_start = get_query_param(next_url, param="start")[0]
        detailed_response = op(start=next_start)
        result = detailed_response.get_result()
        yield detailed_response


def iter_resources(
    op, *, resource_name: str, filter_fn=None, map_fn=None, **kwargs
) -> Iterator:
    """Iterate over the resources, optionally mapped and or filtered."""
    filter_fn = filter_fn or (lambda _: True)
    map_fn = map_fn or (lambda x: x)

    for resp in iter_pages(op, **kwargs):
        resources = resp.get_result().get(resource_name, [])
        yield from map(map_fn, filter(filter_fn, resources))


def get_first(
    op: _IBMCallable,
    *,
    resource_name: str,
    filter_fn: Optional[Callable[..., bool]] = None,
    **kwargs,
) -> Optional[dict]:
    """Get first resource filtered by `filter_fn`."""
    try:
        return next(
            iter_resources(
                op, resource_name=resource_name, filter_fn=filter_fn, **kwargs
            )
        )
    except StopIteration:
        return None


def wait_until(
    check_fn: Callable,
    *args,
    timeout_seconds: int,
    timeout_msg_fn: Callable[..., str],
    raise_on_fail: bool = True,
) -> bool:
    """Wait `timeout_seconds` until `check_fn` evaluates to true."""
    for _ in range(timeout_seconds):
        if check_fn(*args) is True:
            return True
        sleep(1)
    if raise_on_fail:
        raise PycloudlibTimeoutError(timeout_msg_fn())
    return False
