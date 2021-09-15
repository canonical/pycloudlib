# This file is part of pycloudlib. See LICENSE file for license information.
"""Utilities for OCI images and instances."""
import time


def wait_till_ready(func, current_data, desired_state, sleep_seconds=1000):
    """Wait until the results of function call reach a desired lifecycle state.

    Args:
        func: The function to call
        current_data: Structure containing the initial id and lifecycle state
        desired_state: Desired value of "lifecycle_state"
        sleep_seconds: How long to wait in seconds
    Returns:
        The updated version of the current_data
    """
    for _ in range(sleep_seconds):
        current_data = func(current_data.id).data
        if current_data.lifecycle_state == desired_state:
            return current_data
        time.sleep(1)
    raise Exception(
        'Expected {} state, but found {} after waiting {} seconds. '
        'Check OCI console for more details'.format(
            desired_state, current_data.lifecycle_state, sleep_seconds
        )
    )
