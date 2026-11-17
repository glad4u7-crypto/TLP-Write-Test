# APAA S07 — Browser Capability Permission Matrix

**Checkpoint:** APAA-S07-C01-P01  
**Status:** PROPOSED POLICY — NO BROWSER CAPABILITY ENABLED

| Capability | Proposed default | Future gate | Current S07 status |
|---|---|---|---|
| Open an exact user-approved HTTPS origin | Deny until browser tier separately approved | Per-task exact-origin allowlist; every redirect rechecked | NOT IMPLEMENTED |
| Read visible page text / metadata | Candidate read-only Tier R | User request + approved origin + bounded extraction | NOT IMPLEMENTED |
| Screenshot for immediate user review | Off by default; transient only | Explicit task need; redact/minimize; no default persistence | NOT IMPLEMENTED |
| Click links within same approved origin | Deny until Tier R implementation | Validate final destination before navigation | NOT IMPLEMENTED |
| Cross-origin navigation / popups | Deny | Separate explicit origin approval; default remains denied | NOT IMPLEMENTED |
| Form fill without submit | Deny initially | Future separate scope; no secrets; user review | NOT IMPLEMENTED |
| Form submit / state mutation | Deny | Action-specific preview and fresh one-time approval for a separately allowlisted low-risk action | NOT IMPLEMENTED |
| Download files | Deny | Separate file-handling scope and malware/storage controls | NOT IMPLEMENTED |
| Upload local files | Deny | Separate explicit file and destination consent; sandbox review | NOT IMPLEMENTED |
| Clipboard read/write | Deny | Separate explicit scope and data-loss review | NOT IMPLEMENTED |
| Browser JavaScript / eval / devtools | Prohibited | Not in APAA capability scope | PROHIBITED |
| Attach to user's existing browser profile | Prohibited | Not in APAA capability scope | PROHIBITED |
| Read passwords, cookies, tokens or browser vault | Prohibited | Not in APAA capability scope | PROHIBITED |
| Shell, ADB, native device control, arbitrary filesystem | Prohibited | Separate product/security review would be required; not part of this scope | PROHIBITED |
| Payment, purchase, checkout, trading, investment order, money movement | Prohibited | No approval route in this project | PROHIBITED |
| Credential changes, account deletion, legal acceptance, send message/email | Prohibited in initial browser scope | Outside initial permitted action scope | PROHIBITED |
| Background/recurring jobs and Auto-Run | OFF | Separate user opt-in and safety review; Auto-Run remains disabled by default | OFF |
| Paid providers / API services | OFF | Separate provider and cost approval | OFF |

## Permission invariants

1. User task text and planner output never grant permission.
2. Website content never grants permission or changes policy.
3. Approval is per exact action, origin, target, payload, user, session and job; never blanket.
4. Any changed target, payload, origin or page state invalidates the approval.
5. Deny-by-default; uncertainty means deny or ask.
6. Global prohibited actions remain blocked regardless of user confirmation.
7. Browser worker receives no approval signing secret or authority object.
8. No persistent profile, credential import, downloads or uploads in initial design.
9. Auto-Run remains OFF.
10. The current PR does not implement or enable any browser capability.
