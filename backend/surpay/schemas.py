from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class AddressIn(BaseModel):
    """A home the person owned. All parts are required so it can be matched to county records."""

    street: str = Field(min_length=3, max_length=255)
    city: str = Field(min_length=2, max_length=128)
    state: str = Field(min_length=2, max_length=2)
    zip: str = Field(pattern=r"^\d{5}(-\d{4})?$")
    county: str = Field(min_length=2, max_length=64)

    @field_validator("state")
    @classmethod
    def upper_state(cls, v: str) -> str:
        return v.upper()


class AddressOut(BaseModel):
    # No input rules here: addresses saved before a rule existed must still load.
    id: int
    street: str
    city: str
    state: str
    zip: str
    county: str


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=3, max_length=255)
    phone: str = Field(default="", max_length=32)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    token: str
    user: "ProfileOut"


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    other_names: list[str] = Field(default_factory=list, max_length=10)
    phone: str = Field(default="", max_length=32)
    addresses: list[AddressIn] = Field(default_factory=list, max_length=20)


class ProfileOut(BaseModel):
    id: int
    email: str
    full_name: str
    other_names: list[str]
    phone: str
    addresses: list[AddressOut]
    # None (not submitted) | pending | approved | rejected. Matches unlock at "approved".
    identity_status: str | None = None
    identity_note: str = ""
    # Names can't change once ID is submitted: searches use the verified name only.
    name_locked: bool = False


class MatchPreviewOut(BaseModel):
    identity_status: str | None
    possible_matches: int


class LegalOut(BaseModel):
    law: str
    right: str
    process: str
    deadline: str
    proof: list[str]
    note: str
    constitutional: str
    sources: list[str]


class MatchOut(BaseModel):
    record_id: int
    confidence: str  # strong | likely | possible
    address_matched: bool
    state: str
    county: str
    sale_type: str
    reference: str
    owner_name: str
    owner_address: str
    amount_cents: int
    fee_pct: float
    estimated_fee_cents: int
    estimated_net_cents: int
    sale_date: date | None
    source_url: str
    last_seen: datetime
    claim_status: str | None
    legal: LegalOut


class MatchesOut(BaseModel):
    matches: list[MatchOut]
    total_amount_cents: int
    total_estimated_net_cents: int
    records_searched: int
    counties_covered: list[str]
    disclaimer: str = ""


class ClaimIn(BaseModel):
    record_id: int


class TimelineStep(BaseModel):
    status: str
    title: str
    description: str
    state: str  # done | current | upcoming | stopped
    completed_at: datetime | None
    estimate_start: date | None
    estimate_end: date | None


class ClaimOut(BaseModel):
    id: int
    record_id: int
    status: str
    county: str
    state: str
    reference: str
    amount_cents: int
    estimated_net_cents: int
    created_at: datetime
    updated_at: datetime
    next_action: str | None  # verify_identity | sign_agreement | None
    identity_status: str | None  # pending | approved | rejected | None (not submitted)
    identity_note: str
    timeline: list[TimelineStep]
    estimated_completion_start: date | None
    estimated_completion_end: date | None
    disclaimer: str
    legal: LegalOut


class IdentityIn(BaseModel):
    legal_name: str = Field(min_length=3, max_length=255)
    date_of_birth: date
    ssn_last4: str = Field(pattern=r"^\d{4}$")
    phone: str = Field(min_length=7, max_length=32)
    street: str = Field(min_length=3, max_length=255)
    city: str = Field(min_length=2, max_length=128)
    state: str = Field(min_length=2, max_length=2)
    zip: str = Field(pattern=r"^\d{5}(-\d{4})?$")
    id_type: str = Field(pattern=r"^(drivers_license|state_id|passport)$")
    # Base64-encoded JPEG or PNG photos.
    id_front_b64: str = Field(min_length=100)
    id_back_b64: str | None = None
    selfie_b64: str = Field(min_length=100)
    consent: bool
    # Other names they've used (maiden name...). Locked with the legal name once submitted.
    other_names: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("state")
    @classmethod
    def upper_state(cls, v: str) -> str:
        return v.upper()


class AgreementOut(BaseModel):
    version: str
    text: str
    fee_pct: float
    signed: bool
    signature_name: str | None
    signed_at: datetime | None


class SignIn(BaseModel):
    signature_name: str = Field(min_length=3, max_length=255)
    agreed: bool


class AdminStatusIn(BaseModel):
    status: str
    note: str = ""


class AdminIdentityIn(BaseModel):
    decision: str = Field(pattern=r"^(approved|rejected)$")
    note: str = ""


class CoverageOut(BaseModel):
    records: int
    total_amount_cents: int
    counties: list[str]
    demo_login: bool = False

TokenOut.model_rebuild()
