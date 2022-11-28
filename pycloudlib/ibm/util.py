from collections.abc import Callable
from functools import partial
from typing import Iterator, Optional

from ibm_vpc import DetailedResponse

from pycloudlib.util import get_query_param


def iter_pagination(
    op: Callable, *, start: Optional[str] = None, **kwargs
) -> Iterator[DetailedResponse]:
    op = partial(op, **kwargs)
    detailed_response: DetailedResponse = op(start=start)
    yield detailed_response

    while detailed_response.result.get("next") is not None:
        start = get_query_param(detailed_response.result["next"]["href"])[0]
        detailed_response: DetailedResponse = op(start=start)
        yield detailed_response
