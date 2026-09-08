"""Shared pytest fixtures.

Every fixture here points the database module at a throwaway SQLite file inside
a pytest ``tmp_path`` directory, so tests never touch the real
``expense_tracker.db`` in the project root.
"""

import pytest

from database import db as db_module


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Redirect ``database.db.DB_PATH`` at a temp file for the duration of a test."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", path)
    return path


@pytest.fixture
def initialised_db(db_path):
    """A temp database with the schema created but no rows."""
    db_module.init_db()
    return db_path


@pytest.fixture
def seeded_db(initialised_db):
    """A temp database with schema + sample data."""
    db_module.seed_db()
    return initialised_db


@pytest.fixture
def conn(initialised_db):
    """A raw connection to the initialised temp database (FK enforcement on)."""
    connection = db_module._connect()
    yield connection
    connection.close()


@pytest.fixture
def app(seeded_db):
    """The Flask app wired to a seeded temp database, in testing mode."""
    import app as app_module

    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()
