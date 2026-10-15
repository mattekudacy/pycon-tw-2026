import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("DEEPTEAM_TELEMETRY_OPT_OUT", "YES")

import pytest  # noqa: E402

from redteam.judge import JudgeLLM  # noqa: E402


@pytest.fixture(scope="session")
def judge() -> JudgeLLM:
    return JudgeLLM()
