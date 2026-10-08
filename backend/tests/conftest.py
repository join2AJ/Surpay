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


TEST_JPEG = __import__("base64").b64encode(b"\xff\xd8\xff\xe0" + b"0" * 200).decode()


def verify_identity(client, headers, legal_name, approve=True):
    """Submit an ID for the signed-in user and (by default) approve it, as staff would."""
    from surpay import config
    from surpay.db import SessionLocal
    from surpay.models import IdentityVerification

    body = {"legal_name": legal_name, "date_of_birth": "1980-04-02", "ssn_last4": "1234",
            "phone": "555-010-0000", "street": "9 New Home Ln", "city": "Columbus", "state": "OH",
            "zip": "43004", "id_type": "drivers_license", "id_front_b64": TEST_JPEG,
            "selfie_b64": TEST_JPEG, "consent": True}
    r = client.post("/me/identity", headers=headers, json=body)
    assert r.status_code == 200, r.text
    if approve:
        with SessionLocal() as s:
            ident = s.query(IdentityVerification).order_by(IdentityVerification.id.desc()).first()
            ident.review_status = "approved"
            ident.user.full_name = ident.legal_name
            s.commit()
