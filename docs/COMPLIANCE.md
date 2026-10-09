# Security, privacy and compliance

This page maps what Surpay does to DPDP (India), ISO/IEC 27001:2022 and NIST CSF 2.0.

**Being compliant is not something code can do by itself.** DPDP compliance, an ISO 27001 certificate and a NIST CSF profile also need policies, a named owner for each control, staff training, a risk register, vendor contracts and (for ISO) an external audit. This page lists the technical controls that are built, and the organisational work that is still to do.

## What is built

| Area | What Surpay does | Where |
|---|---|---|
| Encryption in transit | HTTPS only (Render TLS). HSTS header on every response | `security.py` |
| Encryption at rest | Neon encrypts the disk (AES-256). On top of that, Surpay encrypts these with Fernet (AES-128-CBC + HMAC-SHA256) before storing them: ID photos, selfies, bar cards, family documents, drawn signatures, chat messages, date of birth, SSN digits, phone, street, city and ZIP | `crypto.py`, `models.py` |
| Key management | Key in `SURPAY_ENCRYPTION_KEY`, separate from the login-token key. On every start the server re-encrypts anything still under an older key (`rotate-keys`). To rotate: set the new key, put the old one in `SURPAY_ENCRYPTION_KEY_OLD`, deploy once, then remove the old one | `crypto.py`, `start.sh` |
| Who can see results | Nobody sees amounts or records until staff approve their photo ID and selfie. Searches use only the name on the verified ID, and names lock once submitted. Family-member searches unlock only after staff check the relationship documents | `api.py`, `me_api.py` |
| Least privilege | Attorneys see a client's details only after accepting the case, and never the client's email or phone. Staff pages need the admin token; every staff view of messages is logged | `attorney_api.py`, `admin_api.py` |
| Audit trail | Every significant action is logged with time, account, IP address, device ID, device model and app version. This covers sign-up, consent, login (including failures), ID submission, signing, messages, status changes, staff decisions, exports and deletions. Each entry contains the SHA-256 of the previous one, so any edit or deletion is detectable (`/admin/audit/verify`) | `audit.py` |
| Proof of who did it | Covered under "Proof of signing" below | `api.py` |
| Authentication | bcrypt password hashes. Login is limited to 8 failures per 15 minutes per IP and per email. Tokens expire after 30 days. "Sign out on all devices" revokes every token | `auth.py`, `security.py` |
| Consent | The Terms of Use and Privacy Notice are versioned. Each acceptance is stored with time, IP and device. Separate consents are recorded for ID processing, each agreement and the attorney terms. People are asked again when a version changes | `policies.py`, `me_api.py` |
| Data principal rights | Covered under "People's rights" below | `me_api.py` |
| Secure headers | `X-Frame-Options: DENY`, `nosniff`, `no-referrer`, `no-store`, a CSP on the admin page | `security.py` |
| Mobile app | No backups of app data (`allowBackup=false`). Photos are kept in the private cache. No third-party analytics or ad SDKs | `AndroidManifest.xml` |

### Proof of signing

Agreements are signed with a typed name that must match the verified ID, plus a signature drawn on screen. Surpay stores:

- the SHA-256 of the exact text signed;
- the drawn signature (encrypted);
- the IP address and device;
- a full audit trail.

Staff can open an evidence certificate for any signed claim at `/admin/claims/{id}/evidence`.

**About IMEI:** Android has not let ordinary apps read the IMEI since Android 10. Instead, the app sends Android's per-app device ID plus a random install ID. Together with the ID photo, the selfie, the matching typed name, the drawn signature, the IP and the hash chain, this ties each submission to one person and one phone.

The strongest remaining addition is phone-number verification by SMS code. It needs an SMS provider such as Twilio.

### People's rights

In the app, under Account → Privacy and data, people can:

- see and download all their data;
- delete their account, and with it withdraw consent. If they have signed a claim, the account is closed and kept for the legal retention period.

Correction and nomination requests go to the Grievance Officer.

## Mapping

### DPDP Act 2023 (India)

The Act applies if Surpay processes personal data in India, for example if the team or servers are there.

| Section | Status |
|---|---|
| §5 Notice | Privacy Notice shown before sign-up, with purposes, data, rights and contact |
| §6 Consent (free, specific, withdrawable) | Separate, versioned and recorded consents. Withdrawal through "Delete my account" |
| §8(5) Security safeguards | Encryption, access control and audit trail (above) |
| §8(6) Breach notice | **To do:** a written breach response plan (who decides, notifying the Board within 72 hours and the people affected) |
| §8(7) Erasure when no longer needed | Deletion flow built. **To do:** a scheduled job to purge closed accounts after the retention period |
| §8(10) Grievance redressal | Contact shown in the app. **To do:** appoint a named Grievance Officer and set `SURPAY_PRIVACY_CONTACT` |
| §11–14 Access, correction, erasure, nomination | Access and erasure in the app. Correction and nomination by request |
| §9 Children | 18+ confirmation at sign-up |
| §16 Transfer outside India | US hosting (Render, Neon). Allowed unless a country is restricted. Review when rules are notified |

### ISO/IEC 27001:2022 Annex A (technical controls)

| Control | Implemented by |
|---|---|
| A.5.15, A.8.2, A.8.3 Access control, privileged access | Verify-first gate, attorney access only after accepting, admin token, document access logged |
| A.5.33, A.8.15 Records and logging | Hash-chained audit log, kept 7 years |
| A.8.5 Secure authentication | bcrypt, rate limits, token expiry and revocation |
| A.8.11 Data masking | Attorneys never receive contact details. Only the last 4 SSN digits are collected |
| A.8.12 Data leakage prevention | Chat blocks phone numbers, emails, links and other apps |
| A.8.24 Cryptography | TLS, Fernet field encryption, key rotation |
| A.8.25–8.29 Secure development, testing | Automated tests on every push (backend and Android end-to-end). Deploys happen only after the tests pass |
| A.8.13 Backup | **To do:** turn on Neon point-in-time restore and test a restore every quarter |

The organisational side is still **to do**:

- information security policy;
- risk assessment and Statement of Applicability;
- asset register;
- supplier agreements (Render, Neon, GitHub);
- staff screening and training;
- incident management;
- internal audit, then a certification audit.

### NIST CSF 2.0

| Function | Built | To do |
|---|---|---|
| Govern | Versioned policies and consent records | Risk owner, policy set, supplier risk |
| Identify | Data inventory (in the Privacy Notice) | Asset register, risk register |
| Protect | Encryption, access control, rate limits, secure headers, no app backups | MFA for staff (put `/admin` behind SSO), dependency scanning |
| Detect | Audit log, failed-login logging, hash-chain check | Alerts on unusual activity (failed logins, mass exports) |
| Respond | Account suspension (token revocation) | Written incident response plan |
| Recover | Database provider redundancy | Tested restores, recovery time targets |

## Before real users (security)

1. Set `SURPAY_ENCRYPTION_KEY` and `SURPAY_ADMIN_TOKEN` on Render. Store a copy of the encryption key somewhere safe and offline.
2. Turn on Neon point-in-time restore.
3. Put `/admin` behind single sign-on with MFA (for example Cloudflare Access) rather than a shared token.
4. Appoint a Grievance Officer and set `SURPAY_PRIVACY_CONTACT` and `SURPAY_SUPPORT_CONTACT`.
5. Have counsel review the Terms, the Privacy Notice, the client agreement and the attorney terms. Each document is versioned, so changing the text re-prompts users.
