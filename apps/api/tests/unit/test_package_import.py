from importlib.metadata import distribution

import dealmind


def test_dealmind_package_import() -> None:
    assert dealmind.__name__ == "dealmind"


def test_package_distribution_is_installed() -> None:
    installed = distribution("dealmind-api")
    assert installed.metadata["Name"] == "dealmind-api"
    assert installed.version
