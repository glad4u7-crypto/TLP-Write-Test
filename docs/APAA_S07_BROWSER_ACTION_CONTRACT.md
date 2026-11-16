# APAA S07 — Proposed Browser Job and Action Contract

**Checkpoint:** APAA-S07-C01-P01  
**Status:** INTERFACE DESIGN ONLY — NO CODE OR HANDLER EXISTS

## 1. Design principles

- The browser worker receives a narrow job description, not a user prompt, approval authority or arbitrary tool access.
- All fields are validated server-side against policy. Unknown fields and unknown action types are rejected.
- The contract is immutable once approved. A changed field requires a new preview and approval.
- Planner-supplied values are proposals; trusted code constructs the final canonical contract.
- No generic "click anything", "run JavaScript", "fetch URL", shell or arbitrary browser-control command is exposed.

## 2. Proposed job envelope

The following is illustrative documentation, not an implemented JSON schema:

```json
{
  "schema_version": "1",
  "job_id": "server-generated-opaque-id",
  "tenant_ref": "server-derived-tenant-reference",
  "session_ref": "server-derived-session-reference",
  "requested_by": "verified-principal-reference",
  "expires_at": "short-lived-timestamp",
  "mode": "read_only",
  "allowed_origins": [
    "https://docs.example.org"
  ],
  "limits": {
    "max_navigation_count": 8,
    "max_requests": 80,
    "max_response_bytes": 2000000,
    "max_runtime_seconds": 60
  },
  "actions": [
    {
      "action_id": "server-generated-step-id",
      "type": "read_visible_text",
      "origin": "https://docs.example.org",
      "path_constraint": "/help/",
      "target": {
        "kind": "semantic_role",
        "role": "main"
      },
      "output_fields": ["visible_text"],
      "approval_ref": null
    }
  ]
}
```

All identifiers, tenant/session references, expiry and limits must be generated or validated by trusted server code. The worker cannot widen its own origin list or quotas.

## 3. Proposed action types

Initial read-only candidate types:
- `navigate_exact_origin`
- `read_visible_text`
- `read_page_title`
- `read_link_metadata`
- `capture_transient_screenshot` (disabled unless explicitly requested)

Not in the initial type system:
- generic click, arbitrary selector execution, JavaScript/eval, arbitrary network request, form submit, download, upload, clipboard access, file chooser, credential entry, browser profile access, CDP or shell.

A future mutation type would need a distinct enum value, exact target and payload fields, a preview representation, action-specific receipt and independent policy eligibility. Do not implement a catch-all `click` or `submit` action.

## 4. Approval binding

The trusted controller should compute a canonical digest over:
- schema version and job ID;
- verified tenant, user, session and expiry;
- exact canonical origin and path constraint;
- action type, target locator and expected effect;
- exact mutation payload or selected fields (if a future mutation is eligible);
- browser context identity and page-state fingerprint;
- policy version and approval expiry.

The receipt must be bound to this digest and consumed once. A new navigation, redirect, target mismatch, changed field value, changed page-state fingerprint or expired job invalidates it. Browser worker must not possess the signing secret or call the approval authority.

## 5. Locator safety

- Prefer semantic role/name and stable visible text over brittle CSS selectors.
- Reject selectors that escape the approved document scope or target hidden/ambiguous elements.
- Require exactly one target match; zero or multiple matches means stop and ask.
- Never infer a submit or destructive control from color, position or vague text.
- Re-resolve and compare target identity immediately before any future approved mutation.

## 6. Worker result envelope

Worker results should be structured and bounded:
- job ID and action ID;
- worker-generated completion status;
- final canonical origin;
- result type and size-limited extracted content;
- timestamps and policy decision reference;
- redaction and truncation flags;
- stable error code on failure.

Worker text is evidence, not authority. Trusted controller records the final lifecycle and audit outcome. Raw cookies, headers containing credentials, request bodies, local file paths and unredacted page bodies are excluded.

## 7. Cancellation and idempotency

- Cancellation, timeout, identity change, authentication expiry, policy failure or worker disconnect revokes the job capability and destroys the context.
- A job ID is single-use. Duplicate submission must not dispatch a second action.
- Read-only retries may be considered only under a future explicit retry policy and strict limits.
- Mutation retries are prohibited by default; ambiguous outcomes require manual review, not blind retry.

## 8. Acceptance tests before implementation

Validate schema strictness, unknown action rejection, exact-origin enforcement, tenant/session binding, approval digest mismatch, target ambiguity, page-state change, expired job, duplicate job, worker result forgery, cancellation and resource limits.
