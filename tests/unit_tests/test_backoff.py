import pytest
from unittest.mock import patch
from pycloudlib.utils.backoff import exponential_backoff
import time


# A helper function to track call counts for testing
class CallTracker:
    def __init__(self, exception=None, fail_times=0):
        self.call_count = 0
        self.exception = exception
        self.fail_times = fail_times

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            if self.exception:
                raise self.exception
        return "Success"


# Class for simpler backoff tests
class TestSimpleBackoff:
    @patch("time.sleep", return_value=None)  # Mock sleep to skip delays
    def test_retry_on_any_exception(self, mock_sleep):
        """
        Tests that the function retries on any exception when no specific
        exception list is provided. It ensures that the exponential backoff
        retries the correct number of times and succeeds if the function
        eventually stops raising exceptions.

        Optimization: time.sleep is mocked to avoid actual delays.
        """
        tracker = CallTracker(exception=Exception, fail_times=2)

        @exponential_backoff(retries=3, base_delay=1)
        def func():
            return tracker()

        result = func()

        assert tracker.call_count == 3
        assert result == "Success"

    @patch("time.sleep", return_value=None)  # Mock sleep to skip delays
    def test_stop_after_max_retries(self, mock_sleep):
        """
        Tests that the function stops retrying after the maximum number of
        retries is reached. It ensures that once the retry limit is hit, the
        last raised exception is propagated. This test verifies that retrying
        is not infinite and respects the retry count.

        Optimization: time.sleep is mocked to avoid actual delays.
        """
        tracker = CallTracker(exception=Exception, fail_times=5)

        @exponential_backoff(retries=3, base_delay=1)
        def func():
            return tracker()

        with pytest.raises(Exception):
            func()

        assert tracker.call_count == 4  # 1 initial attempt + 3 retries

    @patch("time.sleep", return_value=None)  # Mock sleep to skip delays
    def test_retry_on_specific_exceptions(self, mock_sleep):
        """
        Tests that the function only retries when specific exceptions are
        raised. It ensures that the decorator respects the list of exceptions
        to retry on. This is important when handling known, transient errors
        while avoiding retries on other exceptions.

        Optimization: time.sleep is mocked to avoid actual delays.
        """
        tracker = CallTracker(exception=ValueError, fail_times=2)

        @exponential_backoff(retries=3, base_delay=1, exceptions=(ValueError,))
        def func():
            return tracker()

        result = func()

        assert tracker.call_count == 3
        assert result == "Success"

    @patch("time.sleep", return_value=None)  # Mock sleep to skip delays
    def test_does_not_retry_on_unlisted_exception(self, mock_sleep):
        """
        Tests that the function does not retry when an exception is raised that
        is not listed in the retryable exceptions. It ensures that exceptions
        not in the list trigger an immediate failure without retries.

        Optimization: time.sleep is mocked to avoid actual delays.
        """
        tracker = CallTracker(exception=KeyError, fail_times=2)

        @exponential_backoff(retries=3, base_delay=1, exceptions=(ValueError,))
        def func():
            return tracker()

        with pytest.raises(KeyError):
            func()

        assert tracker.call_count == 1

    @patch("time.sleep", return_value=None)  # Mock sleep to skip delays
    def test_no_retries(self, mock_sleep):
        """
        Tests that if retries are set to 0, the function is executed once and
        fails immediately if an exception occurs. This ensures that the backoff
        mechanism doesn't retry when not requested.

        Optimization: time.sleep is mocked to avoid actual delays.
        """
        tracker = CallTracker(exception=Exception, fail_times=1)

        @exponential_backoff(retries=0, base_delay=1)
        def func():
            return tracker()

        with pytest.raises(Exception):
            func()

        assert tracker.call_count == 1

    @patch("time.sleep", return_value=None)  # Mock sleep to skip delays
    def test_success_on_first_attempt(self, mock_sleep):
        """
        Tests that if the function succeeds on the first attempt, no retries
        are made. This ensures that the backoff mechanism does not retry
        unnecessarily when the function succeeds initially.

        Optimization: time.sleep is mocked to avoid actual delays.
        """
        tracker = CallTracker()  # No exception, succeeds immediately

        @exponential_backoff(retries=3, base_delay=1)
        def func():
            return tracker()

        result = func()

        assert tracker.call_count == 1
        assert result == "Success"


# Class for more complex backoff tests involving delay and jitter
class TestBackoffWithDelays:
    @patch("time.sleep", return_value=None)
    def test_base_delay_without_jitter(self, mock_sleep):
        """
        Tests that the base delay is applied without any jitter when jitter is
        disabled. This ensures that the delay doubles as expected without any
        randomization, following the exact exponential backoff pattern.

        Mocks:
        - `time.sleep`: Mocked to avoid actual delays during the test.
        """
        tracker = CallTracker(exception=Exception, fail_times=2)

        @exponential_backoff(retries=3, base_delay=2, jitter=False)
        def func():
            return tracker()

        func()

        assert tracker.call_count == 3

        # Validate that the correct delays (without jitter) were used
        expected_delays = [2, 4]  # Base delay doubles each retry (2, 4)
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]

        assert (
            actual_delays == expected_delays
        ), f"Expected delays {expected_delays}, but got {actual_delays}"

    @patch(
        "random.uniform", side_effect=lambda x, y: x + (y - x) / 2
    )  # Mock random.uniform to return midpoint of range
    @patch("time.sleep", return_value=None)
    def test_jitter_is_applied(self, mock_sleep, mock_random_uniform):
        """
        Tests that jitter is applied to the backoff delay when jitter is
        enabled. This ensures that the exponential backoff introduces a random
        factor in the delay to prevent synchronized retries (thundering herd
        problem).

        Mocks:
        - `random.uniform`: Mocked to control jitter values. In this case, we
          return the midpoint of the jitter range.
        - `time.sleep`: Mocked to avoid actual delays during the test.
        """
        tracker = CallTracker(exception=Exception, fail_times=2)

        @exponential_backoff(retries=3, base_delay=2, jitter=True)
        def func():
            return tracker()

        func()

        assert tracker.call_count == 3

        # Validate that jitter was applied and the delay was randomized
        base_delays = [2, 4]  # Base delays without jitter
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]

        for i, delay in enumerate(actual_delays):
            min_expected = base_delays[i] * 0.5
            max_expected = base_delays[i] * 1.5
            assert (
                min_expected <= delay <= max_expected
            ), f"Delay {delay} not in expected jitter range [{min_expected}, {max_expected}]"

    @patch("time.sleep", return_value=None)
    @patch("time.time")
    def test_max_time_is_respected(self, mock_time, mock_sleep):
        """
        Tests that the total time spent retrying is capped by max_time.
        This ensures that when max_time is reached, retries are stopped
        regardless of how many retries remain.

        Mocks:
        - `time.sleep`: Mocked to avoid actual delays during the test.
        - `time.time`: Mocked to simulate the passage of time.
        """
        # Simulate the passage of time (time starts at 0, and increases on each call)
        mock_time.side_effect = [
            0,
            1,
            2,
            3,
            4,
            5,
            6,
        ]  # Time increases in each step

        tracker = CallTracker(
            exception=Exception, fail_times=10
        )  # Fail more than retries

        @exponential_backoff(
            retries=10, base_delay=2, max_time=5, jitter=False
        )
        def func():
            return tracker()

        # max_time is 5, so it should raise Exception after the time limit is exceeded
        with pytest.raises(
            Exception
        ):  # Should raise after max_time is reached
            func()

        # We expect it to stop before using all retries
        assert tracker.call_count < 10  # It should stop early due to max_time

    @patch("time.sleep", return_value=None)
    def test_no_jitter_when_disabled(self, mock_sleep):
        """
        Tests that no jitter is applied when `jitter=False`. It ensures that
        the backoff follows a strict exponential delay without any randomness.

        Mocks:
        - `time.sleep`: Mocked to avoid actual delays during the test.
        """
        tracker = CallTracker(exception=Exception, fail_times=2)

        @exponential_backoff(retries=3, base_delay=2, jitter=False)
        def func():
            return tracker()

        func()

        assert tracker.call_count == 3

        # Validate that jitter was not applied, and delay is constant
        expected_delays = [2, 4]  # No jitter, so delay is just 2, then 4
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]

        assert (
            actual_delays == expected_delays
        ), f"Expected delays {expected_delays}, but got {actual_delays}"

    @patch(
        "random.uniform", side_effect=[1.2, 1.8]
    )  # Mock random.uniform to return 1.2 and 1.8 for first and second retry
    @patch("time.sleep", return_value=None)
    def test_jitter_randomness(self, mock_sleep, mock_random_uniform):
        """
        Tests that the random jitter differs between retries and is applied
        correctly. This ensures that each retry has a different randomized
        delay based on the jitter factor.

        Mocks:
        - `random.uniform`: Mocked to return specific values for each retry
          (1.2 for first, 1.8 for second).
        - `time.sleep`: Mocked to avoid actual delays during the test.
        """
        tracker = CallTracker(exception=Exception, fail_times=2)

        @exponential_backoff(retries=3, base_delay=2, jitter=True)
        def func():
            return tracker()

        func()

        assert tracker.call_count == 3

        # Expected base delays without jitter
        base_delays = [2, 4]
        # Jittered delays (mocked values from random.uniform)
        expected_delays = [base_delays[0] * 1.2, base_delays[1] * 1.8]

        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]

        assert (
            actual_delays == expected_delays
        ), f"Expected delays {expected_delays}, but got {actual_delays}"
