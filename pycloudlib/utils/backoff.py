# This file is part of pycloudlib. See LICENSE file for license information.
"""Backoff util to retry a function with exponential backoff for specific exceptions."""

import random
import time
from functools import wraps
from typing import Tuple, Type

from pycloudlib.errors import PycloudlibTimeoutError


def exponential_backoff(
    retries=5,
    base_delay=1,
    max_time=None,
    jitter=True,
    exceptions: Tuple[Type[Exception], ...] = (),
):
    """
    Retry a function with exponential backoff for specific exceptions.

    :param retries: Number of retry attempts.
    :param base_delay: Initial delay (in seconds).
    :param max_time: Maximum total time (in seconds) that can elapse before giving up.
    :param jitter: Whether to add random jitter to the delay.
    :param exceptions: A tuple of exception types to retry on. Retries on any exception if empty.
    :return: A decorator that applies exponential backoff to a function.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            last_exception = None

            for retry in range(retries + 1):  # Ensure initial call + retries
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if exceptions and not isinstance(e, exceptions):
                        raise  # Raise immediately if exception is not in the specified exceptions

                    if max_time and (time.time() - start_time) >= max_time:
                        break  # Stop retrying if max_time has elapsed

                    if retry == retries:
                        break  # Do not retry after the last attempt

                    delay = base_delay * (2**retry)
                    if jitter:
                        delay *= random.uniform(0.5, 1.5)

                    # If remaining time is less than the delay, cap it to remaining max_time
                    if max_time:
                        elapsed = time.time() - start_time
                        remaining_time = max_time - elapsed
                        delay = min(delay, remaining_time)

                    print(
                        f"Retry {retry + 1} failed with {type(e).__name__}: {e}, retrying in {delay:.2f} seconds..."
                    )
                    time.sleep(delay)

            # If all retries failed or max_time was reached, raise the last exception
            raise PycloudlibTimeoutError from last_exception

        return wrapper

    return decorator
