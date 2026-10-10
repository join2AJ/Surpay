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
    role: str = Field(default="claimant", pattern=r"^(claimant|attorney)$")
    # Terms of Use and Privacy Notice (current versions) accepted on the sign-up screen.
    accept_terms: bool = False


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
    role: str = "claimant"
    # False when the Terms or Privacy Notice changed since they last accepted: ask again.
    terms_current: bool = True
    unread_notifications: int = 0
    deletion_requested: bool = False


class MatchPreviewOut(BaseModel):
    identity_status: str | None
    possible_matches: int


class LegalOut(BaseModel):
    law: str
    right: str
    process: str
    deadline: str
    if_missed: str = ""
    proof: list[str]
    # Extra proof when claiming for a family member, by basis (heir, power_of_attorney, guardian).
    family_proof: dict[str, list[str]] = Field(default_factory=dict)
    note: str
    facilitator: str = ""
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
    # Approximate last day to claim (from the sale date and state law); None if unknown.
    deadline_date: date | None = None
    # Family claims: whose money this is and how the user is related.
    relative_id: int | None = None
    on_behalf_of: str | None = None


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
    # The partner attorney, once they've accepted the case.
    attorney: "AttorneyPublic | None" = None
    fee_pct: float = 0
    deadline_date: date | None = None
    on_behalf_of: str | None = None
    # Chat with the attorney: open once they accept; they write first.
    chat_open: bool = False
    unread_messages: int = 0
    # False once the county no longer lists the money (often paid out to someone else).
    record_listed: bool = True
    # "SP-000123": quote this to support.
    reference_code: str = ""
    # Documents the attorney asked for (W-9, deed...), and their status.
    document_requests: list[dict] = Field(default_factory=list)


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
    # The typed signature must match this (the name on their verified ID).
    expected_name: str = ""
    document_sha256: str = ""


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class SignIn(BaseModel):
    signature_name: str = Field(min_length=3, max_length=255)
    agreed: bool
    # The signature drawn on screen, as a base64 PNG.
    signature_png_b64: str = Field(min_length=100)


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




class AttorneyPublic(BaseModel):
    """What a claimant sees about their attorney. No contact details: messages go through the app."""
    name: str
    firm: str
    phone: str = ""
    bar: str


class DocumentRequestIn(BaseModel):
    kind: str = Field(max_length=32)
    note: str = Field(default="", max_length=500)


class DocumentUploadIn(BaseModel):
    image_b64: str = Field(min_length=100)


class DocumentReviewIn(BaseModel):
    decision: str = Field(pattern=r"^(accepted|rejected)$")
    note: str = Field(default="", max_length=500)


class AttorneyUpdateIn(BaseModel):
    firm: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, min_length=7, max_length=32)
    office_address: str | None = Field(default=None, min_length=5, max_length=255)
    counties: list[str] | None = Field(default=None, min_length=1, max_length=254)
    available: bool | None = None


class CaseAcceptIn(BaseModel):
    # Rule 1.7: the attorney confirms they checked for conflicts of interest before taking the case.
    conflict_checked: bool = False


class AttorneyApplyIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    bar_state: str = Field(min_length=2, max_length=2)
    bar_number: str = Field(min_length=2, max_length=64)
    firm: str = Field(default="", max_length=255)
    phone: str = Field(min_length=7, max_length=32)
    office_address: str = Field(min_length=5, max_length=255)
    counties: list[str] = Field(min_length=1, max_length=254)
    bar_card_b64: str = Field(min_length=100)
    accept_terms: bool

    @field_validator("bar_state")
    @classmethod
    def upper_state(cls, v: str) -> str:
        return v.upper()


class AttorneyProfileOut(BaseModel):
    available: bool = True
    full_name: str
    bar_state: str
    bar_number: str
    firm: str
    phone: str
    office_address: str
    counties: list[str]
    status: str
    review_note: str
    fee_per_case_cents: int
    terms: str


class CaseOut(BaseModel):
    """A case as an attorney sees it. Claimant details are only filled in after accepting."""
    id: int
    assignment_status: str  # offered | accepted
    status: str
    county: str
    state: str
    reference: str
    sale_type: str
    sale_date: date | None
    amount_cents: int
    fee_cents: int
    payout_status: str
    assigned_at: datetime | None
    accepted_at: datetime | None
    source_url: str
    legal: LegalOut
    on_behalf_of: str | None = None
    # How claims are filed in this state, step by step (and what must be printed).
    filing_guide: dict = Field(default_factory=dict)
    chat_open: bool = False
    unread_messages: int = 0
    # Other accounts that also started a claim on this record (co-owner, heir... or fraud).
    other_claimants: int = 0
    reference_code: str = ""
    document_requests: list[dict] = Field(default_factory=list)
    # After accepting:
    claimant: dict | None = None
    agreement: dict | None = None
    record: dict | None = None
    history: list[dict] = Field(default_factory=list)


class CaseDeclineIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class CaseStatusIn(BaseModel):
    status: str = Field(pattern=r"^(filed|hearing_pending|approved|paid|denied)$")
    note: str = Field(default="", max_length=1000)


class AdminAttorneyIn(BaseModel):
    decision: str = Field(pattern=r"^(approved|rejected)$")
    note: str = ""


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: int
    sender_role: str  # attorney | claimant
    body: str
    created_at: datetime
    read: bool


class ChatOut(BaseModel):
    messages: list[MessageOut]
    can_send: bool
    # Why they can't send yet, e.g. waiting for the attorney's first message.
    waiting_reason: str = ""
    counterpart: str
    code_of_conduct: list[str]


class NotificationOut(BaseModel):
    id: int
    kind: str
    title: str
    body: str
    claim_id: int | None
    created_at: datetime
    read: bool


class NotificationsOut(BaseModel):
    items: list[NotificationOut]
    unread: int


class RelativeIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    other_names: list[str] = Field(default_factory=list, max_length=5)
    relationship: str = Field(pattern=r"^(spouse|parent|child|sibling|grandparent|grandchild|other)$")
    basis: str = Field(pattern=r"^(heir|power_of_attorney|guardian)$")
    date_of_death: date | None = None
    death_certificate_b64: str | None = None
    relationship_proof_b64: str = Field(min_length=100)
    authority_document_b64: str | None = None
    addresses: list[AddressIn] = Field(min_length=1, max_length=10)
    consent: bool


class RelativeOut(BaseModel):
    id: int
    full_name: str
    other_names: list[str]
    relationship: str
    basis: str
    date_of_death: date | None
    review_status: str
    review_note: str
    addresses: list[AddressOut]
    submitted_at: datetime


class PoliciesOut(BaseModel):
    terms_version: str
    terms: str
    privacy_version: str
    privacy: str


class AdminFeeRuleIn(BaseModel):
    state: str = Field(min_length=2, max_length=2)
    county: str = Field(default="", max_length=64)
    base_pct: float | None = Field(default=None, ge=0, le=50)
    legal_max_pct: float | None = Field(default=None, ge=0, le=50)
    legal_source: str = ""
    note: str = ""

    @field_validator("state")
    @classmethod
    def upper_state(cls, v: str) -> str:
        return v.upper()


class AdminFeeBandsIn(BaseModel):
    # [{"up_to_cents": 1000000, "pct": 25}, ..., {"up_to_cents": null, "pct": 12}]
    bands: list[dict] = Field(min_length=1, max_length=10)


class AdminFeeOverrideIn(BaseModel):
    fee_pct: float = Field(ge=0, le=50)
    note: str = ""


TokenOut.model_rebuild()
ClaimOut.model_rebuild()
