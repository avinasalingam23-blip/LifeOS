import pytest
from lifeos.db import Database
from lifeos.service import Service

@pytest.fixture
def db(tmp_path):
    database=Database(tmp_path/'lifeos.sqlite3')
    yield database
    database.close()

@pytest.fixture
def service(db):
    return Service(db)
