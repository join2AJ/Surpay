"""Terms of Use and Privacy Notice shown at sign-up, with versions recorded in each consent.

Have counsel review both before launch. Change the version string whenever the text changes;
people are asked to accept the new version the next time they open the app.
"""

from . import config

TERMS_VERSION = "terms-2026-10"
PRIVACY_VERSION = "privacy-2026-10"


def terms_text() -> str:
    c = config.COMPANY_NAME
    return f"""TERMS OF USE
Version {TERMS_VERSION}

These Terms govern your use of the {c} app and website. By creating an account you agree to them.

1. WHAT {c.upper()} IS
{c} is a technology platform. It helps people find surplus funds that a county or court may be holding in their name, connects them with independent licensed attorneys who file claims, and tracks progress. {c} is not a law firm, does not give legal advice and does not represent you. Any claim is made by you, through the attorney you engage, who is solely responsible for the legal work.

2. WHO MAY USE IT
You must be at least 18 years old. You may search only for yourself, or for a family member where you are their heir or hold legal authority for them and can prove it. You must verify your identity before any results are shown.

3. PROHIBITED USE
You may not use {c} to look up, or claim funds for, anyone you are not entitled to act for. Brokers, finders and other intermediaries may not use claimant accounts. We may suspend accounts that break this rule and keep the records needed to report fraud.

4. YOUR INFORMATION AND DOCUMENTS
Everything you submit must be true, complete and your own (or, for a family member, genuine documents you are entitled to use). Submitting false information or another person's documents may be a crime. Your actions in the app, including the time, IP address and device used, are recorded in a tamper-evident audit log and may be used as evidence of what you submitted and signed.

5. ESTIMATES
Amounts, fees and dates shown are estimates based on public records. They are not a promise. The county or court decides whether and how much is paid.

6. ATTORNEYS
Partner attorneys are independent professionals verified against their state bar. {c} does not supervise or control their legal work and is not responsible for their acts or omissions.

7. MESSAGES
Messages with your attorney stay in the app. Sharing phone numbers, email addresses or links is blocked. Messages are kept with the case record.

8. LIMITATION OF LIABILITY
To the fullest extent permitted by law, {c} provides the service "as is" and is not liable for the outcome of any claim, for decisions of counties or courts, for the acts of attorneys or other users, or for indirect or consequential loss. {c}'s total liability to you will not exceed the fees you have paid to {c} in the twelve months before the claim arose.

9. INDEMNITY
You agree to compensate {c} for losses caused by your breach of these Terms or by false information you provide.

10. ENDING YOUR ACCOUNT
You may close your account at any time in the app (Profile, Privacy and data). We may suspend or close accounts that break these Terms.

11. CHANGES
We may update these Terms. We will ask you to accept material changes before you continue using the app.

12. CONTACT
{config.SUPPORT_CONTACT}
"""


def privacy_text() -> str:
    c = config.COMPANY_NAME
    return f"""PRIVACY NOTICE
Version {PRIVACY_VERSION}

This notice explains what personal data {c} collects, why, and your rights. It is written to meet the Digital Personal Data Protection Act, 2023 (India) and U.S. state privacy laws.

1. WHO IS RESPONSIBLE
{c} is the data fiduciary (controller) for data you give us. Contact: {config.PRIVACY_CONTACT}.

2. WHAT WE COLLECT
- Account: name, email, password (stored only as a one-way hash).
- Identity: legal name, other names, date of birth, last 4 digits of your SSN, phone, current address, ID photos and a selfie.
- Homes: addresses of properties you owned, and for family claims, your relative's details and the documents proving your relationship and authority.
- Claim records: your agreement, drawn signature, case progress and messages with your attorney.
- Security data: IP address, device identifier, device model and app version for each significant action.

3. WHY WE USE IT
Only to verify your identity, find surplus funds in your name, prepare and pursue your claim with your attorney, prevent fraud, keep evidence of what was agreed, and meet legal obligations. We do not sell your data or use it for advertising.

4. WHO SEES IT
Our verification staff; the one attorney who accepts your case (after acceptance only); counties and courts when your claim is filed; service providers who host our systems under contract. Attorneys never see your email address or phone number through {c}.

5. HOW WE PROTECT IT
Data is encrypted in transit (TLS) and at rest. ID images, signatures, messages and identity details are additionally encrypted by {c} before storage. Access is limited to people who need it, and actions are recorded in a tamper-evident audit log.

6. HOW LONG WE KEEP IT
While your account is open and for up to 7 years after your last claim closes, so we can answer disputes and meet legal, tax and audit obligations. Search data with no claim is deleted within 90 days of account closure. Audit records are kept for 7 years.

7. YOUR RIGHTS
You can: see a summary of your data and download a copy (Profile, Privacy and data); correct it (contact us; verified names change only after a new ID check); withdraw consent and ask us to erase your data (Profile, Privacy and data, Delete my account), except what we must keep by law or for an active claim; nominate someone to exercise these rights if you die or become incapacitated (contact us); and complain to our Grievance Officer at {config.PRIVACY_CONTACT}. We reply within 30 days. If you are not satisfied, you can approach the Data Protection Board of India or your state attorney general.

8. CHILDREN
{c} is not for anyone under 18.

9. BREACHES
If a breach affects your data we will tell you and the authorities as the law requires.

10. CHANGES
We will ask you to accept any material change to this notice.
"""
