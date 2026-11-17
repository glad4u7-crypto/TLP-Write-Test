# APAA S09-C01 — Android Integration

**Owner interface:** Android + Termux + Android Chrome (same device)  
**Application form:** Responsive Streamlit web application; not a native APK/PWA.  
**Checkpoint:** `APAA-S09-C01-ANDROID-INTEGRATION`  
**C01 status:** OPEN. Physical acceptance and Owner approval remain pending.

## Architecture decision

Android is the primary Personal Edition Owner control surface. Termux hosts the local application process; Chrome connects to the exact loopback origin on the same phone. The phone is not a browser automation worker.

```text
Owner
  └── Android Chrome
        └── http://127.0.0.1:8501
              └── Streamlit app.py
                    ├── Local Owner authentication
                    ├── Project / task planning UI
                    ├── Explicit approval controls
                    ├── Owner Action History
                    ├── Personal Runtime / SQLite
                    └── Encrypted backup & restore
Termux
  └── hardened launcher + Python runtime
        └── loopback-only Streamlit process

Browser/Worker dispatch: DISABLED
Auto-Run: OFF
```

## Existing Android integration components

| Component | Repository implementation | Current boundary |
|---|---|---|
| Responsive mobile UI | `core/mobile_ui.py` | CSS/layout support; physical touch acceptance still pending |
| Android runtime diagnostic | `scripts/apaa_android_doctor.py` | Read-only; no secrets/personal files read; no app launch |
| Launcher preflight | `scripts/apaa_android_preflight.py` | Validates port, absolute data path, owner-private directory and Streamlit dependency |
| Android launcher | `scripts/apaa_android_start.sh` | Starts Streamlit on `127.0.0.1` only; foreground/manual start |
| Android browser policy | `core/runtime_support.py` | Android browser-worker launch fails closed |
| Owner login and session | `core/personal_auth.py` + app integration | Local Owner passphrase; session expiry/logout enforced |
| Approval and audit | Personal Edition approval/audit modules + Owner UI | Explicit Owner approval; history is available in the authenticated app |
| Backup/restore | P88 encrypted backup implementation | Encrypted portable backup; restore validates archive and uses a fresh signing key |
| Physical test procedure | `docs/APAA_PERSONAL_EDITION_P74_ANDROID_ACCEPTANCE_RUNBOOK.md` | Updated commands and A01–A12 cases; Owner must execute on handset |

## Android integration sequence

1. **Repository preparation:** use the current Personal Edition branch, install the declared dependencies in Termux, and capture the exact commit SHA.
2. **Read-only preflight:** run `python scripts/apaa_android_doctor.py`; do not interpret this as handset acceptance.
3. **Hardened startup:** run `bash scripts/apaa_android_start.sh`; do not bypass its preflight or loopback bind.
4. **Chrome Owner workflow:** open `http://127.0.0.1:8501` on the same phone; verify Owner login, task submission, plan preview, explicit approval/cancel and Action History.
5. **Persistence and recovery:** close/reopen Chrome and manually restart the foreground Termux process; verify permitted state and approval invalidation/recovery behavior.
6. **Encrypted backup drill:** create a synthetic-data encrypted backup and restore to a separate empty directory; verify integrity and project-file hashes.
7. **Physical acceptance:** execute A01–A12 on the actual Android handset and retain only redacted evidence.
8. **Exact-head verification:** run the complete repository CI against the exact resulting branch SHA; keep physical device checks distinct from CI browser emulation.

## Acceptance status

| Gate | Status | Evidence needed |
|---|---|---|
| Responsive mobile layout and automated browser smoke | Implemented; software CI evidence exists on earlier exact heads | Fresh exact-head CI after current changes |
| Hardened Termux launcher and private data path preflight | Implemented | Fresh exact-head CI and actual handset launch |
| Same-device loopback-only Chrome access | Implemented by launcher design | Physical A01–A03 |
| Local Owner login, approval and history workflow | Integrated in app | Physical A02–A10 |
| Restart and persistent state | Personal Runtime implementation exists | Physical A04 and A10 |
| Encrypted backup/restore | P88 implementation exists | Physical A11 on synthetic data |
| Touch, rotation, keyboard and narrow viewport | Responsive CSS and browser smoke exist | Physical A12 |
| Physical Android A01–A12 | **NOT RUN** | Owner-operated handset evidence |
| Android browser-worker support | **UNSUPPORTED / DISABLED** | Not an Android milestone; separate isolated Linux qualification |
| Final C01 Android acceptance | **PENDING** | Physical evidence, exact-head CI, security review and Owner acceptance |

## Non-negotiable safety rules

- Loopback only; no LAN, tunnel or public exposure.
- Local Owner authentication is mandatory; no unauthenticated prototype acceptance.
- Ask First for every supported mutation; Auto-Run OFF.
- No root, APK, accessibility automation, arbitrary shell or device-control bridge.
- No Android-hosted Playwright/Chromium worker. Browser/Worker dispatch stays disabled.
- No payment, purchase, trading or money movement.
- No paid providers/API keys or enterprise infrastructure.
- Do not merge, deploy, enable public browsing or start S09-C02 from this checkpoint.

## Next execution action

Run the updated physical acceptance runbook on the Owner's Android phone, beginning with the read-only runtime diagnostic and hardened launcher. Return only the exact commit SHA, device/runtime versions, PASS/FAIL/BLOCKED outcomes and sanitized error categories. Never share credentials, backup passphrases, cookies, tokens, secrets files or private logs.

**Disposition:** Android integration code and its runbook are present in the Personal Edition branch. This documentation update does not itself prove Android compatibility. S09-C01 remains OPEN; S09-C02 remains NOT STARTED.
