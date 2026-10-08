import pytest

from app.database import create_db_engine
from seed.__main__ import main as seed_main
from tests.helpers import sqlite_url


@pytest.fixture
def db_url(tmp_path):
    """A new, empty SQLite file for each test."""
    return sqlite_url(tmp_path / "seed_test.db")


@pytest.fixture
def engine(db_url):
    engine = create_db_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def run_seed(db_url):
    """Runs the real command:  python -m seed <args>  against the test database."""

    def _run(*args, url=None):
        return seed_main([*args, "--database-url", url or db_url])

    return _run


@pytest.fixture(scope="module")
def seeded_small(tmp_path_factory):
    """One 'small' database with seed 42, shared by the business-scenario tests."""
    url = sqlite_url(tmp_path_factory.mktemp("scenarios") / "scenarios.db")
    assert seed_main(["--size", "small", "--seed", "42", "--database-url", url]) == 0
    engine = create_db_engine(url)
    yield engine
    engine.dispose()
