# Audit, October 2026 (v0.3)

This audit reviewed the backend, the Android app and the legal set-up of Surpay, in three passes:

- a code review for correctness and security;
- a product and UX review;
- a legal review of the flows, from the point of view of a US attorney.

"Fixed" means the fix is built and covered by a test (`backend/tests/test_audit_fixes.py`, plus the Android end-to-end tests). "Open" means the item needs a decision or an outside service.

## Security and correctness

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | The server recorded the IP address the client claimed (`--forwarded-allow-ips='*'`). Anyone could get around the login limit and fake the IP stored with a signature | High | Fixed: the server now takes the address added by Render's proxy |
| 2 | An attorney could jump a case straight to "paid", which falsely told the client "money released" and made the attorney's fee due. Cases could also go backwards | High | Fixed: stages only move forward, in order, and "paid" requires "approved" first |
| 3 | A withdrawn case was still open to its attorney: client documents and chat | High | Fixed: withdrawn cases are closed to attorneys |
| 4 | When a case moved to a new attorney, that attorney saw the previous attorney's private messages, and the client could message them before they introduced themselves | High | Fixed: each attorney has a separate conversation, and the client is notified when the case moves |
| 5 | If an ID was rejected after the agreement was signed, the claim got stuck and never reached an attorney | High | Fixed: the signed agreement is reused if the name still matches; otherwise the client signs again |
| 6 | Setting `SURPAY_ENCRYPTION_KEY` after launch would have made earlier ID photos and details unreadable | High | Fixed: older data still opens, and the server re-encrypts it under the new key on its next start |
| 7 | With no secret key set on a real database, the server silently used a public default | Medium | Fixed: the server refuses to start |
| 8 | When an attorney was suspended, their cases sat unassigned forever | Medium | Fixed: their open cases are offered to another attorney |
| 9 | Deleting an attorney account broke their clients' case records. Closed accounts could still sign in and still received case offers | Medium | Fixed |
| 10 | Photos kept hidden metadata (GPS location, phone serial). A file that only looked like an image was accepted | Medium | Fixed: every photo is re-encoded, which removes the metadata; files that aren't real images are refused |
| 11 | No way to change a password. Common passwords were accepted. Login time revealed which emails have accounts | Medium | Fixed |
| 12 | Updated Terms were enforced only in the app, not by the server | Medium | Fixed: the server enforces them too |
| 13 | Two simultaneous taps could cause server errors (double claim or double signature) | Low | Fixed |
| 14 | Duplicate "please resubmit your ID" notifications | Low | Fixed |
| 15 | App: after signing out, data from the previous person could reappear, the notification counter carried over to the next account, and an expired session just showed errors | Medium | Fixed: everything is cleared and old requests are ignored; an expired session signs out with a message |
| 16 | Requests had no size limit | Low | Fixed: 30 MB maximum |
| 17 | `/admin` uses one shared token, so the audit log can't say which staff member acted | Medium | **Open:** put `/admin` behind single sign-on with 2-step verification (for example Cloudflare Access) |
| 18 | No "forgot password" or email verification | Medium | **Open:** needs an email service (for example Postmark or SES) |
| 19 | There's no SMS check that a phone number belongs to the person | Medium | **Open:** needs an SMS service (for example Twilio) |

## Product

| Change | Status |
|---|---|
| Claimants can no longer cancel in the app (as requested). Cancelling within 3 business days is by written notice to support, as the agreement states, and staff record it on `/admin` | Done |
| One-tap **attorney demo** account: an approved attorney with a verified demo case waiting | Done |
| "Ask for a different attorney" before filing (agreement §3 promises this) | Done |
| Case offers not answered within 3 days go to the next attorney, run by the daily job | Done |
| Warning when the county stops listing a claimant's money | Done |
| Staff see possible duplicate identities (same date of birth plus same name or SSN digits) and records claimed by more than one account | Done |
| Daily erasure of abandoned accounts (180 days) and closed accounts after the 7-year retention period | Done |
| Push notifications arrive within about 15 minutes. Instant delivery needs Firebase Cloud Messaging | Open |
| Other names a claimant declares are searched but not proved. Staff should check them against the ID or a marriage record | Process |

## Legal (attorney's view)

| Topic | Risk | What was done or is still needed |
|---|---|---|
| **The attorney is paid by Surpay, not the client** (ABA Model Rule 1.8(f)) | Rule 1.8(f) requires the client's informed consent, no interference with the attorney's judgment, and confidentiality | **Done:** the agreement now has §3.1 with the client's consent and Surpay's undertakings, and the partner terms state the attorney's duties |
| **Fee-sharing and referral payments** (Rules 5.4, 7.2(b)) | Surpay takes a contingency fee and pays the attorney a flat fee. Some states may treat this as a lawyer sharing fees with a non-lawyer, or as paying for referrals | **Open (critical):** have ethics counsel in each state approve the structure. A common alternative is for the client to sign the attorney's own engagement letter for the legal fee, with Surpay charging separately for its platform service, where state law allows |
| **Conflicts of interest** (Rule 1.7) | An attorney might take a client whose interests conflict with another client or a lienholder | **Done:** attorneys must confirm a conflict check before accepting, which is logged. The case shows when others claim the same record |
| **Surplus "finder" laws** | Several states cap or ban fees for recovering surplus funds, require finders to register, or forbid assigning the funds. Some counties accept claims only from the owner or an attorney | Fee caps are stored per state and county; Colorado is set to 0% and Indiana to 10%. **Open:** a legal survey state by state before entering each state |
| **E-SIGN Act consumer consent** (15 U.S.C. 7001(c)) | Consumers must be told how to get a paper copy and how to withdraw consent to electronic records | **Done:** agreement §11.1 |
| **Unauthorized practice of law** | Explaining "your legal right" could look like legal advice | Every legal screen says it is general information, Surpay is not a law firm, and the attorney confirms what applies. Keep it this way |
| **Cancellation right** | Some states give a cooling-off period for contingency and finder contracts | The agreement keeps a 3-business-day free cancellation by written notice. Staff record it on `/admin` |
| **Heirs** | Other heirs may be entitled, and some counties don't accept powers of attorney | The family-claim flow requires a death certificate, proof of relationship and proof of authority, all reviewed by staff. The attorney sees what is needed for the state |
| **Data privacy** | DPDP (India), state privacy laws, GLBA-style expectations for SSN data | See `docs/COMPLIANCE.md` |

## Before real users: the short list

1. Ethics opinion on the fee structure (Rules 5.4, 7.2 and 1.8(f)), state by state.
2. Counsel to finalise the client agreement, the Terms, the Privacy Notice and the partner terms.
3. Settings on Render:
   - set `SURPAY_ADMIN_TOKEN` and `SURPAY_ENCRYPTION_KEY` (existing data is re-encrypted automatically at the next start);
   - add `SURPAY_ENCRYPTION_KEY` as a GitHub secret too, for the daily job;
   - set `SURPAY_SEED_DEMO=false`.
4. Single sign-on in front of `/admin`, an email service for password reset, and Neon point-in-time restore.
