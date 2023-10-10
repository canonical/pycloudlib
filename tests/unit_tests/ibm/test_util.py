# This file is part of pycloudlib. See LICENSE file for license information.
"""Module for IBM util tests."""
from unittest import mock

import pytest
from ibm_vpc import DetailedResponse
from mock import MagicMock

from pycloudlib.errors import PycloudlibTimeoutError
from pycloudlib.ibm._util import (
    get_first,
    iter_pages,
    iter_resources,
    wait_until,
)

M_PATH = "pycloudlib.ibm._util."


def build_detailed_response(result) -> mock.MagicMock:
    """Build a `DetailedResponse` mock with `result`."""
    response = mock.MagicMock(spec=DetailedResponse)
    response.get_result.return_value = result
    return response


class TestIterPages:
    """`iter_pages` tests."""

    def test_one_page(self):
        """The ibm operation returns one page."""
        response = build_detailed_response({"next": None})
        m_ibm_operation = mock.MagicMock()
        m_ibm_operation.return_value = response

        pages = iter_pages(m_ibm_operation)

        assert response == next(pages)
        assert [mock.call(start=None)] == m_ibm_operation.call_args_list
        with pytest.raises(StopIteration):
            next(pages)

    def test_two_pages(self):
        """The ibm operation returns two page."""
        response_1 = build_detailed_response(
            {"next": {"href": "http://ibm.com/resouce?start=<start_pointer>"}}
        )
        response_2 = build_detailed_response({"next": None})
        m_op = mock.MagicMock()
        m_op.side_effect = (response_1, response_2)

        pages = iter_pages(m_op)

        assert response_1 == next(pages)
        assert [mock.call(start=None)] == m_op.call_args_list

        assert response_2 == next(pages)
        assert [
            mock.call(start=None),
            mock.call(start="<start_pointer>"),
        ] == m_op.call_args_list

        with pytest.raises(StopIteration):
            next(pages)


class TestGetFirst:
    """`get_first` tests."""

    @mock.patch(M_PATH + "iter_pages")
    def test_one_page_no_filter(self, m_iter_pages):
        """The ibm operation returns one page and no filter is applied."""
        m_ibm_operation = mock.MagicMock()
        responses = (build_detailed_response({"resources": ["x", "y"]}),)
        m_iter_pages.return_value = responses
        kwargs = {"a": "a", "b": "b"}

        assert "x" == get_first(
            m_ibm_operation, resource_name="resources", **kwargs
        )
        assert [
            mock.call(m_ibm_operation, **kwargs)
        ] == m_iter_pages.call_args_list

    @mock.patch(M_PATH + "iter_pages")
    def test_one_page_filter(self, m_iter_pages):
        """The ibm operation returns one page and a filter is applied."""
        m_ibm_operation = mock.MagicMock()
        responses = (build_detailed_response({"resources": ["x", "y"]}),)
        m_iter_pages.return_value = responses
        kwargs = {"a": "a", "b": "b"}

        assert "y" == get_first(
            m_ibm_operation,
            resource_name="resources",
            filter_fn=lambda resource: resource == "y",
            **kwargs,
        )
        assert [
            mock.call(m_ibm_operation, **kwargs)
        ] == m_iter_pages.call_args_list


class TestGetAll:
    """`get_all` tests."""

    @mock.patch(M_PATH + "iter_pages")
    def test_two_pages_no_map(self, m_iter_pages):
        """`iter_pages` returns two page and no mapping is applied."""
        m_ibm_operation = mock.MagicMock()
        responses = (
            build_detailed_response({"resources": ["x", "y"]}),
            build_detailed_response({"resources": ["z"]}),
        )
        m_iter_pages.return_value = responses
        kwargs = {"a": "a", "b": "b"}

        assert ["x", "y", "z"] == list(
            iter_resources(
                m_ibm_operation,
                resource_name="resources",
                **kwargs,
            )
        )
        assert [
            mock.call(m_ibm_operation, **kwargs)
        ] == m_iter_pages.call_args_list

    @mock.patch(M_PATH + "iter_pages")
    def test_two_pages_map(self, m_iter_pages):
        """`iter_pages` returns two page and a mapping is applied."""
        m_ibm_operation = mock.MagicMock()
        responses = (
            build_detailed_response({"resources": ["x", "y"]}),
            build_detailed_response({"resources": ["z"]}),
        )
        m_iter_pages.return_value = responses
        kwargs = {"a": "a", "b": "b"}

        assert ["x^^", "y^^", "z^^"] == list(
            iter_resources(
                m_ibm_operation,
                resource_name="resources",
                map_fn=lambda resource: resource + "^^",
                **kwargs,
            )
        )
        assert [
            mock.call(m_ibm_operation, **kwargs)
        ] == m_iter_pages.call_args_list


class TestWaitUntil:
    """`wait_until` tests."""

    @mock.patch(M_PATH + "sleep")
    def test_eventual_true(self, m_sleep):
        """`check_fn` does succeed after 3 calls."""
        check_fn = MagicMock()
        check_fn.side_effect = (False, False, True)

        assert True is wait_until(
            check_fn=check_fn,
            timeout_seconds=20,
            timeout_msg_fn=lambda: "<msg>",
        )
        assert [mock.call(1), mock.call(1)] == m_sleep.call_args_list

    @mock.patch(M_PATH + "sleep")
    def test_false_raises(self, m_sleep):
        """`check_fn` never succeed and exception is raised."""
        check_fn = MagicMock()
        check_fn.return_value = False

        with pytest.raises(PycloudlibTimeoutError, match="<msg>"):
            wait_until(
                check_fn=check_fn,
                timeout_seconds=20,
                timeout_msg_fn=lambda: "<msg>",
                raise_on_fail=True,
            )
        assert [mock.call(1)] * 20 == m_sleep.call_args_list

    @mock.patch(M_PATH + "sleep")
    def test_false(self, m_sleep):
        """`check_fn` never succeed and exception is never raised."""
        check_fn = MagicMock()
        check_fn.return_value = False

        assert False is wait_until(
            check_fn=check_fn,
            timeout_seconds=20,
            timeout_msg_fn=lambda: "<msg>",
            raise_on_fail=False,
        )
        assert [mock.call(1)] * 20 == m_sleep.call_args_list
