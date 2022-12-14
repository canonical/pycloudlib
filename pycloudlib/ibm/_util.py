# This file is part of pycloudlib. See LICENSE file for license information.
"""Private utilities for IBM cloud."""
from functools import partial
from time import sleep
from typing import Callable, Iterator, List, Optional, TypeVar

from ibm_vpc import DetailedResponse

from pycloudlib.util import get_query_param

_IBMCallable = Callable[..., DetailedResponse]


class IBMException(Exception):
    """IBM exception root."""


def iter_pages(
    op: _IBMCallable, *, start: Optional[str] = None, **kwargs
) -> Iterator[DetailedResponse]:
    """Lazily iterate over a paginated endpoint."""
    op = partial(op, **kwargs)
    detailed_response: DetailedResponse = op(start=start)
    yield detailed_response

    while detailed_response.result.get("next") is not None:
        start = get_query_param(
            detailed_response.result["next"]["href"], param="start"
        )[0]
        detailed_response = op(start=start)
        yield detailed_response


def get_first(
    op: _IBMCallable,
    *,
    resource_name: str,
    filter_fn: Optional[Callable[..., bool]] = None,
    **kwargs,
) -> Optional[dict]:
    """Get first resource filtered by `filter_fn`."""
    filter_fn = filter_fn or (lambda x: x)
    for resp in iter_pages(op, **kwargs):
        resources = resp.get_result().get(resource_name, [])
        try:
            resource = next(filter(filter_fn, resources))
        except StopIteration:
            continue  # Jump to next page
        return resource

    return None


U = TypeVar("U")
V = TypeVar("V")


def get_all(
    op: _IBMCallable,
    *,
    resource_name: str,
    map_fn: Optional[Callable[[U], V]] = None,
    **kwargs,
) -> List[V]:
    """Get all resources, optionally mapped by `map_fn`."""
    map_fn = map_fn or (lambda x: x)

    result: List[V] = []
    for resp in iter_pages(op, **kwargs):
        resources = resp.get_result().get(resource_name, [])
        result.extend(map(map_fn, resources))
    return result


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
        raise TimeoutError(timeout_msg_fn())
    return False
