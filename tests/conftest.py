import os

import pytest

from laya_top.models import Identity, Process


@pytest.fixture
def process():
    return Process(
        Identity(424242, 1700000000),
        1,
        "python3.12",
        "/usr/local/bin/python3.12",
        "tester",
        os.getuid(),
        25.0,
        150 * 1024**2,
        "running",
        3,
    )
