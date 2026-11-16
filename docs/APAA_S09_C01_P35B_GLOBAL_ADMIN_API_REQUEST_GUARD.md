# APAA P35-B — Global Admin API Request Guard

**Status:** reusable request-authorization primitive implemented; no HTTP API routes exist to wire; Global Owner remains inactive.  
**PR:** #11 — Draft / Open / Unmerged  
**Date:** 2026-11-16

## Implementation

Added `core/global_admin_api_guard.py` and focused tests.

`GlobalAdminRequestAuthorizer` is a framework-neutral boundary for future privileged API handlers. Every handler must call `authorize(principal)` for every privileged request. The guard:

- accepts a Principal only from trusted authentication middleware;
- invokes a trusted server-side owner-configuration loader on every call;
- requires the exact configured OIDC issuer + subject pair;
- denies missing, malformed, unprovisioned, changed or unavailable configuration;
- does not cache owner authorization or configuration;
- returns only the validated Principal and emits generic denial messages without exposing loader details.

Tests cover owner re-key becoming effective on the next request, old-owner denial, missing/invalid config, loader failures, non-owner and unauthenticated principals, and invalid construction.

## Critical integration boundary

Repository inspection found no separate HTTP API router or Global Admin API endpoint in the current application. The current UI is Streamlit. Therefore this change supplies a tested authorization primitive but **does not claim endpoint integration**. When a real API router is introduced, every privileged read and mutation route must invoke this guard after trusted authentication and before reading or mutating protected data. UI visibility is not authorization.

The loader must read authoritative protected server-side configuration afresh. The guard now also requires a durable generation reader and denies requests when configuration and generation disagree. See P35-C for the same-host SQLite CAS/high-water primitive and its limitations. This does not create a distributed API deployment or independently durable anti-rollback anchor.

## Not implemented / blocked

- No Global Admin API route, admin UI, bootstrap, recovery or re-key endpoint.
- No external append-only owner audit sink or independently administered anti-rollback anchor; the P35-C local SQLite audit/generation primitive is not tamper-proof.
- No live OIDC, physical Android, production Linux host or independent security review.
- No owner identity, token, secret, API key or private key was added.

## Safety disposition

This primitive does not activate Global Owner. PR #11 must remain Draft/Open/Unmerged; no merge, deployment, production activation, Auto-Run, worker/browser activation, paid API or payment. S09-C01 remains OPEN / NOT COMPLETE; S09-C02 must not start.
