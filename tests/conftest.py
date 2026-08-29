"""Test environment isolation.

Several modules build boto3 clients. boto3 takes its region and credentials
from the environment, so without this the suite passes on a machine with AWS
configured and fails in CI, where nothing is -- a failure that says nothing
about the code under test.

Pinning fake values cuts both ways. The suite no longer depends on the
machine it runs on, and code that reaches past its mock cannot reach real AWS
with a real developer's credentials: it gets an invalid-token error instead
of touching a live account. That matters more here than in most of this
portfolio, because one of the tools issues refunds.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_FAKE_ENV = {
    "AWS_DEFAULT_REGION": "ap-south-1",
    "AWS_REGION": "ap-south-1",
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_EC2_METADATA_DISABLED": "true",
}

# Cleared rather than set. botocore resolves an empty AWS_PROFILE as a profile
# literally named "" and raises ProfileNotFound before it ever reaches the
# region, so unsetting it is the only way to stop a developer's named profile
# leaking into the suite.
_CLEARED = ("AWS_PROFILE",)


@pytest.fixture(scope="session", autouse=True)
def aws_test_environment() -> Iterator[None]:
    previous = {k: os.environ.get(k) for k in (*_FAKE_ENV, *_CLEARED)}
    for key in _CLEARED:
        os.environ.pop(key, None)
    for key, value in _FAKE_ENV.items():
        os.environ.setdefault(key, value)
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
