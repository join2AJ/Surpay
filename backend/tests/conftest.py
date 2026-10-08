import os
import tempfile

os.environ["SURPAY_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ.setdefault("SURPAY_SECRET_KEY", "test-secret")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from surpay.api import app  # noqa: E402
from surpay.db import Base, SessionLocal, engine, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    init_db()
    yield


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
