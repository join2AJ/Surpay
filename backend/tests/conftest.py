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


@pytest.fixture(autouse=True)
def no_rate_limits():
    from surpay.security import login_limiter
    login_limiter.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def real_image(fmt: str = "JPEG", color=(30, 110, 80), size=(64, 40)) -> str:
    """A small, genuine image as base64 (uploads are decoded and re-encoded, so fakes are refused)."""
    import base64
    import io

    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format=fmt)
    return base64.b64encode(out.getvalue()).decode()


SIGNATURE_PNG = real_image("PNG", (255, 255, 255), (120, 40))
TEST_JPEG = real_image()


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
