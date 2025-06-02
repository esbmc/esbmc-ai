# Author: Yiannis Charalambous

import pytest
import structlog


@pytest.fixture(autouse=True, scope="session")
def silence_structlog() -> None:
    structlog.configure(
        logger_factory=structlog.ReturnLoggerFactory(),
        processors=[],
    )
