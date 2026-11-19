# APAA Browser Automation — Architecture Decision Records

**Project:** Personal AI Automation Agent (APAA)  
**Roadmap:** S09 Browser Automation / C01 Browser Foundation  
**Date:** 2026-11-19  
**Status:** Accepted target decisions; implementation and release qualification remain gated.

This document is the concise decision register for the production architecture. The normative component contracts, capability matrix, lifecycle, evidence envelope, network policy and completion checklist are in `APAA_BROWSER_AUTOMATION_PRODUCTION_ARCHITECTURE.md`.

## ADR-001 — Owner-first trust model
**Decision:** Owner is the root of authorization. No anonymous/public access by default. Every job is bound to Owner, tenant/project and session.  
**Reason:** A natural-language planner and website content are not authorities.  
**Consequences:** Approval receipts must be fresh, one-time and job/action/origin-bound. Access delegation is explicit and revocable.  
**Status:** Design accepted; full release acceptance remains open.

## ADR-002 — Separate planning from execution
**Decision:** Planner emits a typed bounded proposal; policy gate independently authorizes it; browser controller executes only typed capabilities.  
**Reason:** Prevent prompt/page content from directly invoking privileged actions.  
**Consequences:** No arbitrary shell, JavaScript evaluation, raw CDP or unrestricted Playwright interface.

## ADR-003 — Separate navigation, inspection and mutation
**Decision:** These are distinct capabilities with independent checks.  
**Reason:** Read access must not imply permission to alter a website.  
**Consequences:** Fresh origin/target evidence and action-specific approval are required before mutation. Upload/download and financial actions remain denied by default or prohibited.

## ADR-004 — Ephemeral isolated worker
**Decision:** One job uses one disposable non-root worker with immutable image identity, dedicated namespaces, read-only root, no capabilities, seccomp, no-new-privileges and bounded resources.  
**Reason:** Browser content and browser vulnerabilities are hostile.  
**Consequences:** Local Playwright launch is only a development foundation, not the production isolation boundary. A concrete backend must be independently reviewed.

## ADR-005 — Proxy-only dual-stack egress
**Decision:** Worker egress is default-DROP for IPv4 and IPv6; exact pinned TCP proxy endpoints only. DNS is proxy-side; TLS validation remains in Chromium.  
**Reason:** Prevent direct egress, DNS rebinding paths, UDP/QUIC bypass and proxy fallback.  
**Consequences:** The current nftables parser's IPv4-only rule grammar is insufficient; dual-stack parser/provider/fixtures and real-host evidence are required before this decision can be considered implemented.

## ADR-006 — Independent attestation
**Decision:** Browser starts only after fresh signed evidence from a trusted host/runtime observer, bound to a one-time challenge and immutable launch spec.  
**Reason:** Worker-supplied claims and cached snapshots are not proof.  
**Consequences:** Runtime provider, authenticated control channel, key custody/rotation/restore and challenge consumption must be implemented and tested.

## ADR-007 — Fail closed and preserve uncertainty
**Decision:** Missing approval, stale evidence, runtime mismatch, timeout, crash or unconfirmed cleanup blocks success. Uncertain non-idempotent actions become UNKNOWN and are never blindly replayed.  
**Reason:** False success and duplicate mutations are unacceptable.  
**Consequences:** Recovery and audit are part of the execution transaction.

## ADR-008 — Android is not automatically the browser host
**Decision:** Android is the Owner client/control plane unless a separate supported and qualified browser-host architecture is approved.  
**Reason:** Android/Termux compatibility cannot be inferred from Python tests or desktop OCI qualification.  
**Consequences:** Preserve the existing fail-closed platform guard; device testing occurs only after software work and explicit Owner instruction.

## ADR-009 — Financial actions are prohibited
**Decision:** No payment, checkout, purchase, trading or money movement. No paid provider/API provisioning.  
**Reason:** Explicit project safety boundary.  
**Consequences:** These actions cannot be enabled by a website, prompt, approval or configuration switch.

## Decision status
The target architecture decisions are recorded. This is not a production-readiness statement. Current known implementation blockers include dual-stack nftables evidence parsing, concrete production worker backend and runtime observation, authenticated worker control channel, complete launch-spec mapping, operational key lifecycle, unresolved Chromium FD ownership failure, real-host network qualification, Android qualification and independent Owner acceptance. Browser/Worker remain disabled; Auto-Run remains OFF.
