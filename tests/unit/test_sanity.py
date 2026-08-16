"""M0 sanity: package imports and the test harness itself runs.
Real unit tests arrive with each milestone's code."""
import taxi_mlops


def test_package_imports():
    assert taxi_mlops.__doc__ is not None
