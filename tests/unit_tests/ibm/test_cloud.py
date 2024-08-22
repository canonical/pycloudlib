# This file is part of pycloudlib. See LICENSE file for license information.
"""Module for IBM cloud tests."""

from typing import List
from unittest import mock

import pytest

from pycloudlib.errors import InvalidTagNameError, PycloudlibTimeoutError
from pycloudlib.ibm.cloud import (
    IBM,
)

M_PATH = "pycloudlib.ibm._util."

rule1 = "All letters must be lowercase"
rule2 = "Must be between 1 and 63 characters long"
rule3 = "Must not start or end with a hyphen"
rule4 = "Must be alphanumeric and hyphens only"
rule5 = "Must start with a letter"


@pytest.mark.parametrize(
    "tag, rules_failed",
    [
        ("tag123", []),
        ("123tag", [rule5]),
        ("TAG", [rule1]),
        ("TAG-", [rule1, rule3]),
        ("-tag_", [rule3, rule4]),
        ("-", [rule3]),
        ("x" * 64, [rule2]),
        ("", [rule2]),
        ("x" * 63, []),
        ("x", []),
        ("1t a_g-", [rule3, rule4, rule5]),
    ],
)
def test_validate_tag(tag: str, rules_failed: List[str]):
    if len(rules_failed) == 0:
        # test that no exception is raised
        IBM._validate_tag(tag)
    else:
        with pytest.raises(InvalidTagNameError) as exc_info:
            IBM._validate_tag(tag)
        assert tag in str(exc_info.value)
        for rule in rules_failed:
            assert rule in str(exc_info.value)
