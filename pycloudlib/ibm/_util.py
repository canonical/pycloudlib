from functools import partial
from time import sleep
from typing import Callable, Iterator, List, Optional, TypeVar

from ibm_vpc import DetailedResponse

from pycloudlib.util import get_query_param


class IBMException(Exception):
    ...


def iter_pages(
    op: Callable, *, start: Optional[str] = None, **kwargs
) -> Iterator[DetailedResponse]:
    op = partial(op, **kwargs)
    detailed_response: DetailedResponse = op(start=start)
    yield detailed_response

    while detailed_response.result.get("next") is not None:
        start = get_query_param(detailed_response.result["next"]["href"])[0]
        detailed_response: DetailedResponse = op(start=start)
        yield detailed_response


def get_first(
    op: Callable,
    *,
    resource_name: str,
    filter_fn: Optional[Callable[..., bool]] = None,
    **kwargs,
) -> Optional[dict]:
    filter_fn = filter_fn or (lambda x: x)
    for resp in iter_pages(op, **kwargs):
        resources = resp.get_result().get(resource_name, [])
        try:
            resource = next(filter(filter_fn, resources))
        except StopIteration:
            continue  # Jump to next page
        return resource

    return None


T = TypeVar("T")


def get_all(
    op: Callable,
    *,
    resource_name: str,
    map_fn: Optional[Callable[[dict], T]] = None,
    **kwargs,
) -> List[T]:
    map_fn = map_fn or (lambda x: x)

    result: List[T] = []
    for resp in iter_pages(op, **kwargs):
        resources = resp.get_result().get(resource_name, [])
        result.extend(map(map_fn, resources))
    return result


def wait_until(
    check_fn: Callable,
    *args,
    timeout_seconds: int,
    timeout_msg_fn: str,
    raise_on_fail: bool = True,
) -> Iterator:
    for _ in range(timeout_seconds):
        if check_fn(*args) == True:
            return True
        sleep(1)
    if raise_on_fail:
        raise TimeoutError(timeout_msg_fn())
    return False
