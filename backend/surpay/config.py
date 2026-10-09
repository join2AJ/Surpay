import os
import warnings


def _database_url() -> str:
    url = os.environ.get("SURPAY_DATABASE_URL") or os.environ.get("DATABASE_URL") or "sqlite:///./surpay.db"
    # Render, Neon and Heroku hand out postgres:// URLs; SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _database_url()

SECRET_KEY = os.environ.get("SURPAY_SECRET_KEY", "")
if not SECRET_KEY:
    if not DATABASE_URL.startswith("sqlite"):
        # A public default would let anyone forge sign-in tokens and decrypt stored documents.
        raise RuntimeError("SURPAY_SECRET_KEY must be set when using a real database")
    SECRET_KEY = "dev-only-insecure-secret-change-me"
    warnings.warn("SURPAY_SECRET_KEY is not set; using an insecure development key (local SQLite only).")

# Testing only: fictional Demo County records and a one-tap demo account. Off for real users.
DEMO_ENABLED = os.environ.get("SURPAY_SEED_DEMO", "false").lower() == "true"

# Key for encrypting ID documents at rest. Falls back to SECRET_KEY; never change it once
# documents are stored, or they can no longer be read.
ENCRYPTION_KEY = os.environ.get("SURPAY_ENCRYPTION_KEY", "") or SECRET_KEY
# Previous key while rotating (see surpay/crypto.py). Leave empty normally.
ENCRYPTION_KEY_OLD = os.environ.get("SURPAY_ENCRYPTION_KEY_OLD", "")

# Token for the staff review page (/admin). Admin endpoints are off when it's empty.
ADMIN_TOKEN = os.environ.get("SURPAY_ADMIN_TOKEN", "")

# What Surpay pays a partner attorney per case, by state, in cents. PLACEHOLDER: set from your
# attorney agreements. Paid once the county or court releases the funds.
DEFAULT_ATTORNEY_FEE_CENTS = int(os.environ.get("SURPAY_ATTORNEY_FEE_CENTS", "50000"))
STATE_ATTORNEY_FEE_CENTS: dict[str, int] = {}


def attorney_fee_for(state: str) -> int:
    return STATE_ATTORNEY_FEE_CENTS.get(state.upper(), DEFAULT_ATTORNEY_FEE_CENTS)


TOKEN_TTL_DAYS = int(os.environ.get("SURPAY_TOKEN_TTL_DAYS", "30"))

# Identify the scraper honestly to county webmasters.
USER_AGENT = os.environ.get(
    "SURPAY_USER_AGENT",
    "SurpayBot/0.1 (+https://github.com/join2AJ/Surpay; surplus-funds research)",
)

# Starting contingency fee when no county or state rule is set. The fee actually quoted for a
# case comes from surpay/fees.py (county rate, amount band and legal cap, set by staff).
DEFAULT_FEE_PCT = 15.0

# Who people contact about their data (DPDP "grievance officer" / privacy contact).
COMPANY_NAME = os.environ.get("SURPAY_COMPANY_NAME", "Surpay")
PRIVACY_CONTACT = os.environ.get("SURPAY_PRIVACY_CONTACT", "privacy@surpay.app")
SUPPORT_CONTACT = os.environ.get("SURPAY_SUPPORT_CONTACT", "support@surpay.app")

# Proxies in front of the API that append to X-Forwarded-For (Render: 2, its edge and its load balancer). Used to find the
# caller's real IP for rate limits and the audit trail without trusting client-sent values.
PROXY_HOPS = int(os.environ.get("SURPAY_PROXY_HOPS", "2"))
