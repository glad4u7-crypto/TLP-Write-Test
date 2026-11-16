# APAA-S09-C01-P53 — Remote monotonic anchor preflight

**Status:** read-only operator tool and tests committed; exact-head CI pending.  
**Production qualification:** NOT CLAIMED.

Added `scripts/check_apaa_remote_anchor.py`. It accepts the HTTPS endpoint, CA, mTLS client certificate/key, owner-anchor ID and trust-bundle issuer ID. It performs only authenticated GET requests through `HTTPSMonotonicAnchor` and prints the current owner revision and trust sequence.

The output explicitly marks write testing as NOT_RUN, backup/restore anti-rollback as NOT_ASSESSED, independent administration as NOT_ASSESSED, independent review as PENDING and production qualification as NOT_QUALIFIED.

The tool does not bootstrap, mutate, advance, reset or delete anchor state. It does not prove atomic CAS, durability, administrator separation, provider backup/restore behavior or immutable audit history. Those require provider-specific tests and independent evidence.

Tests cover successful sanitized output and fail-closed sanitized error handling. No external endpoint, credentials, service or account was used.
