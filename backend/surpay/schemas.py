from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class AddressIn(BaseModel):
    street: str = Field(min_length=3, max_length=255)
    city: str = Field(default="", max_length=128)
    state: str = Field(min_length=2, max_length=2)
    zip: str = Field(default="", max_length=10)

    @field_validator("state")
    @classmethod
    def upper_state(cls, v: str) -> str:
        return v.upper()


class AddressOut(AddressIn):
    id: int


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


class MatchesOut(BaseModel):
    matches: list[MatchOut]
    total_amount_cents: int
    total_estimated_net_cents: int
    records_searched: int
    counties_covered: list[str]


class ClaimIn(BaseModel):
    record_id: int


class ClaimOut(BaseModel):
    id: int
    record_id: int
    status: str
    county: str
    state: str
    reference: str
    amount_cents: int
    created_at: datetime
    updated_at: datetime


class CoverageOut(BaseModel):
    records: int
    total_amount_cents: int
    counties: list[str]

TokenOut.model_rebuild()
